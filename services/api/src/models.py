import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    source_type = Column(Enum("rtsp", "usb", name="source_type_enum"), nullable=False)
    source_uri = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    frame_interval_ms = Column(Integer, default=1000, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    plate_records = relationship("PlateRecord", back_populates="camera")


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_url = Column(String(500), nullable=False)
    title = Column(String(300), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    status = Column(
        Enum("pending", "downloading", "processing", "completed", "failed", name="video_job_status_enum"),
        default="pending",
        nullable=False,
    )
    progress = Column(Float, default=0.0, nullable=False)
    total_frames = Column(Integer, default=0, nullable=False)
    processed_frames = Column(Integer, default=0, nullable=False)
    plates_found = Column(Integer, default=0, nullable=False)
    frame_interval_sec = Column(Float, default=1.0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    plate_records = relationship("PlateRecord", back_populates="video_job")

    __table_args__ = (
        Index("idx_video_job_status", "status"),
    )


class PlateRecord(Base):
    __tablename__ = "plate_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=True)
    video_job_id = Column(UUID(as_uuid=True), ForeignKey("video_jobs.id"), nullable=True)
    plate_number = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    source = Column(Enum("camera", "upload", "youtube", name="record_source_enum", create_constraint=False), nullable=False)
    image_path = Column(String(500), nullable=False)
    plate_region = Column(JSONB, nullable=True)
    frame_timestamp = Column(Float, nullable=True)
    recognized_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    camera = relationship("Camera", back_populates="plate_records")
    video_job = relationship("VideoJob", back_populates="plate_records")

    __table_args__ = (
        Index("idx_plate_number", "plate_number"),
        Index("idx_recognized_at", "recognized_at"),
        Index("idx_camera_recognized", "camera_id", "recognized_at"),
        Index("idx_plate_video_job", "video_job_id"),
    )
