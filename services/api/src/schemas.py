from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str = Field(max_length=100)
    source_type: str = Field(pattern="^(rtsp|usb)$")
    source_uri: str = Field(max_length=500)
    frame_interval_ms: int = Field(default=1000, ge=100)


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    source_type: str | None = Field(default=None, pattern="^(rtsp|usb)$")
    source_uri: str | None = Field(default=None, max_length=500)
    frame_interval_ms: int | None = Field(default=None, ge=100)


class CameraRead(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    source_uri: str
    is_active: bool
    frame_interval_ms: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlateRecordRead(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID | None
    video_job_id: uuid.UUID | None
    plate_number: str
    confidence: float
    source: str
    image_path: str
    plate_region: dict[str, Any] | None
    frame_timestamp: float | None
    recognized_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None


class PaginatedResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None


# --- VideoJob Schemas ---


class VideoJobCreate(BaseModel):
    youtube_url: str = Field(max_length=500)
    frame_interval_sec: float = Field(default=1.0, ge=0.1, le=30.0)


class VideoJobRead(BaseModel):
    id: uuid.UUID
    youtube_url: str
    title: str | None
    duration_seconds: int | None
    status: str
    progress: float
    total_frames: int
    processed_frames: int
    plates_found: int
    frame_interval_sec: float
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class VideoJobDetail(VideoJobRead):
    plates: list[dict[str, Any]] = []
