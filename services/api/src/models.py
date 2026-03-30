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


class PlateRecord(Base):
    __tablename__ = "plate_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=True)
    plate_number = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    source = Column(Enum("camera", "upload", name="record_source_enum"), nullable=False)
    image_path = Column(String(500), nullable=False)
    plate_region = Column(JSONB, nullable=True)
    recognized_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    camera = relationship("Camera", back_populates="plate_records")

    __table_args__ = (
        Index("idx_plate_number", "plate_number"),
        Index("idx_recognized_at", "recognized_at"),
        Index("idx_camera_recognized", "camera_id", "recognized_at"),
    )
