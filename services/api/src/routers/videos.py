import json
import os
import uuid

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PlateRecord, VideoJob
from ..schemas import ApiResponse, PaginatedResponse, VideoJobCreate, VideoJobRead

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])

redis_client = redis_lib.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
)

QUEUE_KEY = "queue:video_jobs"


@router.post("", response_model=ApiResponse, status_code=202)
def create_video_job(body: VideoJobCreate, db: Session = Depends(get_db)):
    job = VideoJob(
        youtube_url=body.youtube_url,
        frame_interval_sec=body.frame_interval_sec,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    message = json.dumps({
        "job_id": str(job.id),
        "youtube_url": body.youtube_url,
        "frame_interval_sec": body.frame_interval_sec,
    })
    redis_client.lpush(QUEUE_KEY, message)

    return ApiResponse(
        success=True,
        data=VideoJobRead.model_validate(job).model_dump(mode="json"),
    )


@router.get("", response_model=PaginatedResponse)
def list_video_jobs(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(VideoJob)
    if status:
        query = query.filter(VideoJob.status == status)
    total = query.count()
    jobs = query.order_by(desc(VideoJob.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(
        success=True,
        data=[VideoJobRead.model_validate(j).model_dump(mode="json") for j in jobs],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.get("/{job_id}", response_model=ApiResponse)
def get_video_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    plates = (
        db.query(PlateRecord)
        .filter(PlateRecord.video_job_id == job_id)
        .order_by(PlateRecord.frame_timestamp)
        .all()
    )
    plate_list = [
        {
            "plate_number": p.plate_number,
            "confidence": p.confidence,
            "frame_timestamp": p.frame_timestamp,
        }
        for p in plates
    ]

    data = VideoJobRead.model_validate(job).model_dump(mode="json")
    data["plates"] = plate_list

    return ApiResponse(success=True, data=data)


@router.delete("/{job_id}", response_model=ApiResponse)
def delete_video_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    db.delete(job)
    db.commit()
    return ApiResponse(success=True, data={"deleted": str(job_id)})
