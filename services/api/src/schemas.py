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
    plate_number: str
    confidence: float
    source: str
    image_path: str
    plate_region: dict[str, Any] | None
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
