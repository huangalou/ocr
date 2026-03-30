import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Camera
from ..schemas import ApiResponse, CameraCreate, CameraRead, CameraUpdate

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


@router.get("", response_model=ApiResponse)
def list_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).order_by(Camera.created_at.desc()).all()
    return ApiResponse(
        success=True,
        data=[CameraRead.model_validate(c).model_dump(mode="json") for c in cameras],
    )


@router.post("", response_model=ApiResponse, status_code=201)
def create_camera(body: CameraCreate, db: Session = Depends(get_db)):
    camera = Camera(**body.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return ApiResponse(
        success=True,
        data=CameraRead.model_validate(camera).model_dump(mode="json"),
    )


@router.put("/{camera_id}", response_model=ApiResponse)
def update_camera(camera_id: uuid.UUID, body: CameraUpdate, db: Session = Depends(get_db)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(camera, key, value)
    db.commit()
    db.refresh(camera)
    return ApiResponse(
        success=True,
        data=CameraRead.model_validate(camera).model_dump(mode="json"),
    )


@router.delete("/{camera_id}", response_model=ApiResponse)
def delete_camera(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    db.delete(camera)
    db.commit()
    return ApiResponse(success=True, data={"deleted": str(camera_id)})


@router.post("/{camera_id}/toggle", response_model=ApiResponse)
def toggle_camera(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera.is_active = not camera.is_active
    db.commit()
    db.refresh(camera)
    return ApiResponse(
        success=True,
        data=CameraRead.model_validate(camera).model_dump(mode="json"),
    )
