import csv
import io
import json
import os
import uuid
from datetime import datetime

import redis as redis_lib
from boto3 import client as boto3_client
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PlateRecord
from ..schemas import ApiResponse, PaginatedResponse, PlateRecordRead

router = APIRouter(prefix="/api/v1/plates", tags=["plates"])

redis_client = redis_lib.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
)

minio_client = boto3_client(
    "s3",
    endpoint_url=f"http://{os.environ.get('MINIO_HOST', 'minio')}:{os.environ.get('MINIO_PORT', 9000)}",
    aws_access_key_id=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
    aws_secret_access_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
)

MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "ocr-images")


@router.get("", response_model=PaginatedResponse)
def list_plates(
    plate_number: str | None = None,
    camera_id: uuid.UUID | None = None,
    source: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_confidence: float | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="recognized_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    query = db.query(PlateRecord)
    if plate_number:
        query = query.filter(PlateRecord.plate_number.ilike(f"%{plate_number}%"))
    if camera_id:
        query = query.filter(PlateRecord.camera_id == camera_id)
    if source:
        query = query.filter(PlateRecord.source == source)
    if start_date:
        query = query.filter(PlateRecord.recognized_at >= start_date)
    if end_date:
        query = query.filter(PlateRecord.recognized_at <= end_date)
    if min_confidence is not None:
        query = query.filter(PlateRecord.confidence >= min_confidence)

    total = query.count()
    sort_col = getattr(PlateRecord, sort_by, PlateRecord.recognized_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse(
        success=True,
        data=[PlateRecordRead.model_validate(r).model_dump(mode="json") for r in records],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.get("/export")
def export_plates(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    plate_number: str | None = None,
    camera_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(PlateRecord)
    if plate_number:
        query = query.filter(PlateRecord.plate_number.ilike(f"%{plate_number}%"))
    if camera_id:
        query = query.filter(PlateRecord.camera_id == camera_id)
    if start_date:
        query = query.filter(PlateRecord.recognized_at >= start_date)
    if end_date:
        query = query.filter(PlateRecord.recognized_at <= end_date)
    records = query.order_by(desc(PlateRecord.recognized_at)).all()

    if format == "json":
        return JSONResponse(
            content=[PlateRecordRead.model_validate(r).model_dump(mode="json") for r in records]
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "plate_number", "confidence", "source", "camera_id", "recognized_at"])
    for r in records:
        writer.writerow([
            str(r.id), r.plate_number, r.confidence,
            r.source, str(r.camera_id) if r.camera_id else "",
            r.recognized_at.isoformat(),
        ])
    output.seek(0)
    return StreamingResponse(
        output, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plates.csv"},
    )


@router.post("/upload", response_model=ApiResponse, status_code=202)
async def upload_image(file: UploadFile, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    contents = await file.read()
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    object_key = f"uploads/{job_id}.{ext}"

    minio_client.put_object(
        Bucket=MINIO_BUCKET, Key=object_key, Body=contents,
        ContentType=file.content_type or "image/jpeg",
    )
    message = json.dumps({
        "job_id": job_id, "image_path": object_key,
        "source": "upload", "camera_id": None,
    })
    redis_client.lpush("queue:frames", message)

    return ApiResponse(success=True, data={"job_id": job_id, "image_path": object_key})


@router.get("/{record_id}", response_model=ApiResponse)
def get_plate(record_id: uuid.UUID, db: Session = Depends(get_db)):
    record = db.query(PlateRecord).filter(PlateRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return ApiResponse(
        success=True,
        data=PlateRecordRead.model_validate(record).model_dump(mode="json"),
    )
