# YouTube License Plate Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YouTube video analysis — users submit a YouTube URL, the system downloads the video, extracts frames, and runs them through the existing OCR pipeline to identify license plates.

**Architecture:** New Video Worker microservice (yt-dlp + OpenCV) consumes a dedicated Redis queue, extracts frames into the existing `queue:frames` pipeline. API Service gets a new videos router + WebSocket channel. Frontend gets a new YouTube analysis page.

**Tech Stack:** yt-dlp, OpenCV, Redis, PostgreSQL, MinIO (existing); new Docker service

---

## Task 1: Shared Constants & Environment Variables

**Files:**
- Modify: `shared/constants.py`
- Modify: `.env.example`

- [ ] **Step 1: Update shared/constants.py**

Add these constants after the existing ones:

```python
REDIS_QUEUE_VIDEO_JOBS = "queue:video_jobs"
REDIS_CHANNEL_VIDEO_PROGRESS = "channel:video_progress"
VIDEO_STREAM_THRESHOLD_SEC = 300
```

- [ ] **Step 2: Update .env.example**

Add at the end:

```env
VIDEO_STREAM_THRESHOLD_SEC=300
VIDEO_FRAME_INTERVAL_SEC=1.0
```

- [ ] **Step 3: Update .env (local copy)**

```bash
echo "" >> .env
echo "VIDEO_STREAM_THRESHOLD_SEC=300" >> .env
echo "VIDEO_FRAME_INTERVAL_SEC=1.0" >> .env
```

- [ ] **Step 4: Commit**

```bash
git add shared/constants.py .env.example
git commit -m "feat: add YouTube video job constants and env vars"
```

---

## Task 2: Database Migration — video_jobs Table & plate_records Changes

**Files:**
- Modify: `services/api/src/models.py`
- New migration via Alembic

- [ ] **Step 1: Update services/api/src/models.py**

Add the VideoJob model and update PlateRecord. The full file becomes:

```python
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
```

- [ ] **Step 2: Generate migration**

```bash
docker-compose exec api alembic revision --autogenerate -m "add video_jobs table and plate_records youtube fields"
```

- [ ] **Step 3: Manually edit the generated migration**

The autogenerated migration won't handle the ENUM modification correctly. Edit the migration file to handle the source enum change properly:

After the autogenerated content, add at the top of `upgrade()`:

```python
# Add 'youtube' to the existing record_source_enum
op.execute("ALTER TYPE record_source_enum ADD VALUE IF NOT EXISTS 'youtube'")
```

- [ ] **Step 4: Run migration**

```bash
docker-compose exec api alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add services/api/src/models.py migrations/
git commit -m "feat: add video_jobs table and YouTube fields to plate_records"
```

---

## Task 3: API Service — Video Schemas

**Files:**
- Modify: `services/api/src/schemas.py`

- [ ] **Step 1: Add video schemas to services/api/src/schemas.py**

Append after the existing `PaginatedResponse` class:

```python
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
```

Note: The existing `PlateRecordRead` class must be **replaced** with the updated version above (adds `video_job_id` and `frame_timestamp`).

- [ ] **Step 2: Commit**

```bash
git add services/api/src/schemas.py
git commit -m "feat: add VideoJob schemas and update PlateRecordRead"
```

---

## Task 4: API Service — Videos Router

**Files:**
- Create: `services/api/src/routers/videos.py`
- Modify: `services/api/src/main.py`

- [ ] **Step 1: Create services/api/src/routers/videos.py**

```python
import json
import os
import uuid

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PlateRecord, VideoJob
from ..schemas import ApiResponse, PaginatedResponse, VideoJobCreate, VideoJobDetail, VideoJobRead

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
```

- [ ] **Step 2: Update services/api/src/main.py**

```python
import asyncio

from fastapi import FastAPI

from .routers import cameras, plates, videos
from .websocket import redis_subscriber, video_progress_subscriber, websocket_endpoint, video_websocket_endpoint

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)
app.include_router(plates.router)
app.include_router(videos.router)
app.add_api_websocket_route("/api/v1/ws/plates", websocket_endpoint)
app.add_api_websocket_route("/api/v1/ws/videos/{job_id}", video_websocket_endpoint)


@app.on_event("startup")
async def startup():
    asyncio.create_task(redis_subscriber())
    asyncio.create_task(video_progress_subscriber())


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Commit**

```bash
git add services/api/src/routers/videos.py services/api/src/main.py
git commit -m "feat: videos CRUD router and main.py registration"
```

---

## Task 5: API Service — Video WebSocket

**Files:**
- Modify: `services/api/src/websocket.py`

- [ ] **Step 1: Replace services/api/src/websocket.py**

```python
import asyncio
import json
import os
from collections import defaultdict

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

REDIS_URL = f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', 6379)}"


class PlateWebSocketManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, data: dict):
        message = json.dumps(data)
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                self._connections.remove(ws)


class VideoWebSocketManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[job_id].append(ws)

    def disconnect(self, job_id: str, ws: WebSocket):
        if job_id in self._connections:
            self._connections[job_id].remove(ws)
            if not self._connections[job_id]:
                del self._connections[job_id]

    async def send_to_job(self, job_id: str, data: dict):
        message = json.dumps(data)
        for ws in list(self._connections.get(job_id, [])):
            try:
                await ws.send_text(message)
            except Exception:
                self._connections[job_id].remove(ws)


plate_manager = PlateWebSocketManager()
video_manager = VideoWebSocketManager()


async def redis_subscriber():
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:plate_recognized")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await plate_manager.broadcast(data)
            video_job_id = data.get("video_job_id")
            if video_job_id:
                await video_manager.send_to_job(video_job_id, {
                    "type": "plate_found",
                    "plate_number": data["plate_number"],
                    "confidence": data["confidence"],
                    "frame_timestamp": data.get("frame_timestamp"),
                })


async def video_progress_subscriber():
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:video_progress")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            job_id = data.get("job_id")
            if job_id:
                await video_manager.send_to_job(job_id, data)


async def websocket_endpoint(ws: WebSocket):
    await plate_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        plate_manager.disconnect(ws)


async def video_websocket_endpoint(ws: WebSocket, job_id: str):
    await video_manager.connect(job_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        video_manager.disconnect(job_id, ws)
```

- [ ] **Step 2: Commit**

```bash
git add services/api/src/websocket.py
git commit -m "feat: video progress WebSocket with per-job routing"
```

---

## Task 6: OCR Service — Support video_job_id, frame_timestamp, and Dedup

**Files:**
- Modify: `services/ocr/src/db.py`
- Modify: `services/ocr/src/main.py`

- [ ] **Step 1: Update services/ocr/src/db.py**

```python
import json
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{os.environ['POSTGRES_DB']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def is_duplicate_plate(video_job_id: str, plate_number: str) -> bool:
    if not video_job_id:
        return False
    session = SessionLocal()
    try:
        result = session.execute(
            text(
                "SELECT 1 FROM plate_records "
                "WHERE video_job_id = :video_job_id AND plate_number = :plate_number "
                "LIMIT 1"
            ),
            {"video_job_id": uuid.UUID(video_job_id), "plate_number": plate_number},
        )
        return result.fetchone() is not None
    finally:
        session.close()


def save_plate_record(
    plate_number: str,
    confidence: float,
    source: str,
    image_path: str,
    plate_region: dict | None = None,
    camera_id: str | None = None,
    video_job_id: str | None = None,
    frame_timestamp: float | None = None,
) -> dict:
    session = SessionLocal()
    try:
        record_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                "INSERT INTO plate_records "
                "(id, camera_id, video_job_id, plate_number, confidence, source, image_path, plate_region, frame_timestamp, recognized_at, created_at) "
                "VALUES "
                "(:id, :camera_id, :video_job_id, :plate_number, :confidence, :source, :image_path, CAST(:plate_region AS jsonb), :frame_timestamp, :recognized_at, :created_at)"
            ),
            {
                "id": record_id,
                "camera_id": uuid.UUID(camera_id) if camera_id else None,
                "video_job_id": uuid.UUID(video_job_id) if video_job_id else None,
                "plate_number": plate_number,
                "confidence": confidence,
                "source": source,
                "image_path": image_path,
                "plate_region": json.dumps(plate_region) if plate_region else None,
                "frame_timestamp": frame_timestamp,
                "recognized_at": now,
                "created_at": now,
            },
        )
        session.commit()
        return {
            "id": str(record_id),
            "plate_number": plate_number,
            "confidence": confidence,
            "recognized_at": now.isoformat(),
            "video_job_id": video_job_id,
            "frame_timestamp": frame_timestamp,
        }
    finally:
        session.close()
```

- [ ] **Step 2: Update services/ocr/src/main.py**

```python
import json
import logging
import os

import redis as redis_lib

from .db import is_duplicate_plate, save_plate_record
from .recognizer import recognize_plate
from .storage import download_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ocr-service")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "ocr-images")
CONFIDENCE_THRESHOLD = float(os.environ.get("OCR_CONFIDENCE_THRESHOLD", 0.6))

QUEUE_KEY = "queue:frames"
PUBSUB_CHANNEL = "channel:plate_recognized"


def main():
    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    logger.info("OCR service started, waiting for frames...")

    while True:
        result = r.brpop(QUEUE_KEY, timeout=5)
        if result is None:
            continue

        _, raw = result
        message = json.loads(raw)
        job_id = message.get("job_id", "unknown")
        image_path = message["image_path"]
        source = message.get("source", "camera")
        camera_id = message.get("camera_id")
        video_job_id = message.get("video_job_id")
        frame_timestamp = message.get("frame_timestamp")

        logger.info(f"Processing job {job_id}: {image_path}")

        try:
            image_bytes = download_image(MINIO_BUCKET, image_path)
        except Exception:
            logger.exception(f"Failed to download image: {image_path}")
            continue

        plates = recognize_plate(image_bytes, CONFIDENCE_THRESHOLD)

        if not plates:
            logger.info(f"No plates found in {image_path}")
            continue

        for plate in plates:
            if is_duplicate_plate(video_job_id, plate["plate_number"]):
                logger.info(f"Skipping duplicate plate {plate['plate_number']} for video job {video_job_id}")
                continue

            record = save_plate_record(
                plate_number=plate["plate_number"],
                confidence=plate["confidence"],
                source=source,
                image_path=image_path,
                plate_region=plate["plate_region"],
                camera_id=camera_id,
                video_job_id=video_job_id,
                frame_timestamp=frame_timestamp,
            )
            logger.info(f"Saved plate: {plate['plate_number']} (conf={plate['confidence']})")

            r.publish(PUBSUB_CHANNEL, json.dumps(record))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add services/ocr/src/db.py services/ocr/src/main.py
git commit -m "feat: OCR service supports video_job_id, frame_timestamp, and dedup"
```

---

## Task 7: Video Worker Service

**Files:**
- Create: `services/video-worker/requirements.txt`
- Create: `services/video-worker/Dockerfile`
- Create: `services/video-worker/src/__init__.py`
- Create: `services/video-worker/src/progress.py`
- Create: `services/video-worker/src/downloader.py`
- Create: `services/video-worker/src/extractor.py`
- Create: `services/video-worker/src/main.py`

- [ ] **Step 1: Create services/video-worker/requirements.txt**

```
yt-dlp==2024.12.23
opencv-python-headless==4.10.0.84
redis==5.2.1
psycopg2-binary==2.9.10
sqlalchemy==2.0.36
boto3==1.36.4
numpy==1.26.4
```

- [ ] **Step 2: Create services/video-worker/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/video-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/video-worker/src ./src
COPY shared ./shared

CMD ["python", "-m", "src.main"]
```

- [ ] **Step 3: Create services/video-worker/src/__init__.py**

Empty file.

- [ ] **Step 4: Create services/video-worker/src/progress.py**

```python
import json
import os
import uuid
from datetime import datetime, timezone

import redis as redis_lib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{os.environ['POSTGRES_DB']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
CHANNEL = "channel:video_progress"

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    return _redis


def update_job(job_id: str, **kwargs):
    session = SessionLocal()
    try:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        params = {k: v for k, v in kwargs.items()}
        params["job_id"] = uuid.UUID(job_id)
        session.execute(text(f"UPDATE video_jobs SET {sets} WHERE id = :job_id"), params)
        session.commit()
    finally:
        session.close()

    msg = {"job_id": job_id, **{k: v for k, v in kwargs.items() if k != "error_message"}}
    if "status" in kwargs:
        msg["type"] = kwargs["status"] if kwargs["status"] in ("completed", "failed") else "progress"
    else:
        msg["type"] = "progress"
    if "error_message" in kwargs:
        msg["error"] = kwargs["error_message"]
    _get_redis().publish(CHANNEL, json.dumps(msg, default=str))


def update_progress(job_id: str, processed_frames: int, total_frames: int, plates_found: int):
    progress = processed_frames / total_frames if total_frames > 0 else 0.0
    update_job(
        job_id,
        processed_frames=processed_frames,
        total_frames=total_frames,
        plates_found=plates_found,
        progress=round(progress, 4),
    )


def mark_completed(job_id: str, plates_found: int):
    update_job(
        job_id,
        status="completed",
        progress=1.0,
        plates_found=plates_found,
        completed_at=datetime.now(timezone.utc),
    )


def mark_failed(job_id: str, error: str):
    update_job(
        job_id,
        status="failed",
        error_message=error,
        completed_at=datetime.now(timezone.utc),
    )
```

- [ ] **Step 5: Create services/video-worker/src/downloader.py**

```python
import logging
import os
import tempfile

import yt_dlp

logger = logging.getLogger(__name__)

VIDEO_STREAM_THRESHOLD_SEC = int(os.environ.get("VIDEO_STREAM_THRESHOLD_SEC", 300))


def get_video_info(url: str) -> dict:
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Unknown"),
            "duration_seconds": int(info.get("duration", 0)),
        }


def download_video(url: str, output_dir: str) -> str:
    output_path = os.path.join(output_dir, "video.%(ext)s")
    ydl_opts = {
        "format": "best[height<=720]",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        logger.info(f"Downloaded video to {filename}")
        return filename


def get_stream_url(url: str) -> str:
    ydl_opts = {
        "format": "best[height<=720]",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]


def should_stream(duration_seconds: int) -> bool:
    return duration_seconds > VIDEO_STREAM_THRESHOLD_SEC
```

- [ ] **Step 6: Create services/video-worker/src/extractor.py**

```python
import logging
import math
import os
import uuid

import cv2
from boto3 import client as boto3_client

logger = logging.getLogger(__name__)

MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "ocr-images")

_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3_client(
            "s3",
            endpoint_url=f"http://{os.environ['MINIO_HOST']}:{os.environ['MINIO_PORT']}",
            aws_access_key_id=os.environ["MINIO_ROOT_USER"],
            aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        )
    return _s3


def extract_frames(video_path: str, job_id: str, frame_interval_sec: float, queue_push_fn):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 30.0

    frame_skip = max(1, int(fps * frame_interval_sec))
    total_extract_frames = math.ceil(total_video_frames / frame_skip)

    logger.info(f"Video: {total_video_frames} frames, {fps:.1f} fps, extracting every {frame_skip} frames (~{total_extract_frames} frames)")

    extracted = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_skip == 0:
            timestamp = frame_idx / fps
            _, buffer = cv2.imencode(".jpg", frame)
            image_bytes = buffer.tobytes()

            object_key = f"videos/{job_id}/frame_{extracted:05d}.jpg"
            _get_s3().put_object(
                Bucket=MINIO_BUCKET,
                Key=object_key,
                Body=image_bytes,
                ContentType="image/jpeg",
            )

            queue_push_fn(object_key, timestamp)
            extracted += 1

        frame_idx += 1

    cap.release()
    return extracted, total_extract_frames
```

- [ ] **Step 7: Create services/video-worker/src/main.py**

```python
import json
import logging
import os
import tempfile

import redis as redis_lib

from .downloader import download_video, get_stream_url, get_video_info, should_stream
from .extractor import extract_frames
from .progress import mark_completed, mark_failed, update_job, update_progress

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("video-worker")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_KEY = "queue:video_jobs"
FRAMES_QUEUE_KEY = "queue:frames"

PROGRESS_UPDATE_INTERVAL = 5


def main():
    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    logger.info("Video worker started, waiting for jobs...")

    while True:
        result = r.brpop(QUEUE_KEY, timeout=5)
        if result is None:
            continue

        _, raw = result
        message = json.loads(raw)
        job_id = message["job_id"]
        youtube_url = message["youtube_url"]
        frame_interval_sec = message.get("frame_interval_sec", 1.0)

        logger.info(f"Processing video job {job_id}: {youtube_url}")

        try:
            update_job(job_id, status="downloading")

            info = get_video_info(youtube_url)
            update_job(
                job_id,
                title=info["title"],
                duration_seconds=info["duration_seconds"],
            )
            logger.info(f"Video: {info['title']} ({info['duration_seconds']}s)")

            update_job(job_id, status="processing")

            extracted_count = 0
            plates_count = 0

            def push_frame(image_path: str, timestamp: float):
                nonlocal extracted_count
                frame_msg = json.dumps({
                    "job_id": job_id,
                    "image_path": image_path,
                    "source": "youtube",
                    "camera_id": None,
                    "video_job_id": job_id,
                    "frame_timestamp": round(timestamp, 2),
                })
                r.lpush(FRAMES_QUEUE_KEY, frame_msg)
                extracted_count += 1

                if extracted_count % PROGRESS_UPDATE_INTERVAL == 0:
                    update_progress(job_id, extracted_count, total_frames, plates_count)

            if should_stream(info["duration_seconds"]):
                stream_url = get_stream_url(youtube_url)
                total_frames = int(info["duration_seconds"] / frame_interval_sec)
                update_job(job_id, total_frames=total_frames)
                extracted, _ = extract_frames(stream_url, job_id, frame_interval_sec, push_frame)
            else:
                with tempfile.TemporaryDirectory() as tmpdir:
                    video_path = download_video(youtube_url, tmpdir)
                    total_frames = int(info["duration_seconds"] / frame_interval_sec)
                    update_job(job_id, total_frames=total_frames)
                    extracted, _ = extract_frames(video_path, job_id, frame_interval_sec, push_frame)

            update_progress(job_id, extracted, extracted, plates_count)
            mark_completed(job_id, plates_count)
            logger.info(f"Video job {job_id} completed: {extracted} frames extracted")

        except Exception as e:
            logger.exception(f"Video job {job_id} failed")
            mark_failed(job_id, str(e))


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Commit**

```bash
git add services/video-worker/
git commit -m "feat: video worker service with yt-dlp download and frame extraction"
```

---

## Task 8: Docker Compose — Add Video Worker

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Add video-worker to docker-compose.yml**

Add before the `volumes:` section:

```yaml
  video-worker:
    build:
      context: .
      dockerfile: services/video-worker/Dockerfile
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./services/video-worker/src:/app/src
      - ./shared:/app/shared
```

- [ ] **Step 2: Add video-worker to docker-compose.prod.yml**

Add before the `volumes:` section:

```yaml
  video-worker:
    build:
      context: .
      dockerfile: services/video-worker/Dockerfile
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 1G
    restart: unless-stopped
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml docker-compose.prod.yml
git commit -m "feat: add video-worker service to Docker Compose"
```

---

## Task 9: Frontend — API Client & WebSocket Hook for Videos

**Files:**
- Modify: `services/frontend/src/api/client.ts`
- Create: `services/frontend/src/hooks/useVideoWebSocket.ts`

- [ ] **Step 1: Update services/frontend/src/api/client.ts**

Add the VideoJob interface and update PlateRecord. Append after existing exports:

```typescript
export interface VideoJob {
  id: string;
  youtube_url: string;
  title: string | null;
  duration_seconds: number | null;
  status: "pending" | "downloading" | "processing" | "completed" | "failed";
  progress: number;
  total_frames: number;
  processed_frames: number;
  plates_found: number;
  frame_interval_sec: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  plates?: { plate_number: string; confidence: number; frame_timestamp: number }[];
}

// Videos
export const createVideoJob = (data: { youtube_url: string; frame_interval_sec?: number }) =>
  api.post<ApiResponse<VideoJob>>("/videos", data);
export const listVideoJobs = (params?: Record<string, string | number>) =>
  api.get<PaginatedResponse<VideoJob>>("/videos", { params });
export const getVideoJob = (id: string) =>
  api.get<ApiResponse<VideoJob>>(`/videos/${id}`);
export const deleteVideoJob = (id: string) =>
  api.delete<ApiResponse<{ deleted: string }>>(`/videos/${id}`);
```

Also update the `PlateRecord` interface `source` field:

```typescript
  source: "camera" | "upload" | "youtube";
```

- [ ] **Step 2: Create services/frontend/src/hooks/useVideoWebSocket.ts**

```typescript
import { useEffect, useRef, useState, useCallback } from "react";

export interface VideoProgressMessage {
  type: "progress" | "plate_found" | "completed" | "failed";
  status?: string;
  progress?: number;
  processed_frames?: number;
  plates_found?: number;
  plate_number?: string;
  confidence?: number;
  frame_timestamp?: number;
  error?: string;
}

export function useVideoWebSocket(jobId: string | null) {
  const [messages, setMessages] = useState<VideoProgressMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!jobId) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/videos/${jobId}`);

    ws.onmessage = (event) => {
      const data: VideoProgressMessage = JSON.parse(event.data);
      setMessages((prev) => [...prev, data]);
    };

    ws.onclose = () => {
      setTimeout(connect, 3000);
    };

    wsRef.current = ws;
  }, [jobId]);

  useEffect(() => {
    if (jobId) {
      setMessages([]);
      connect();
    }
    return () => wsRef.current?.close();
  }, [jobId, connect]);

  return messages;
}
```

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/api/client.ts services/frontend/src/hooks/useVideoWebSocket.ts
git commit -m "feat: frontend video API client and WebSocket hook"
```

---

## Task 10: Frontend — YouTube Analysis Page

**Files:**
- Create: `services/frontend/src/pages/YouTubeAnalysis.tsx`
- Modify: `services/frontend/src/App.tsx`

- [ ] **Step 1: Create services/frontend/src/pages/YouTubeAnalysis.tsx**

```tsx
import { useEffect, useState } from "react";
import { createVideoJob, listVideoJobs, getVideoJob, deleteVideoJob } from "../api/client";
import type { VideoJob } from "../api/client";
import { useVideoWebSocket } from "../hooks/useVideoWebSocket";
import type { VideoProgressMessage } from "../hooks/useVideoWebSocket";

export default function YouTubeAnalysis() {
  const [url, setUrl] = useState("");
  const [interval, setInterval_] = useState(1.0);
  const [submitting, setSubmitting] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<VideoJob | null>(null);
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [plates, setPlates] = useState<{ plate_number: string; confidence: number; frame_timestamp: number }[]>([]);

  const messages = useVideoWebSocket(activeJobId);

  const refreshJobs = () => listVideoJobs().then((res) => setJobs(res.data.data));

  useEffect(() => { refreshJobs(); }, []);

  useEffect(() => {
    if (!messages.length) return;
    const latest = messages[messages.length - 1];

    if (latest.type === "progress" && activeJob) {
      setActiveJob((prev) => prev ? {
        ...prev,
        status: latest.status || prev.status,
        progress: latest.progress ?? prev.progress,
        processed_frames: latest.processed_frames ?? prev.processed_frames,
        plates_found: latest.plates_found ?? prev.plates_found,
      } : prev);
    }

    if (latest.type === "plate_found" && latest.plate_number) {
      setPlates((prev) => [...prev, {
        plate_number: latest.plate_number!,
        confidence: latest.confidence || 0,
        frame_timestamp: latest.frame_timestamp || 0,
      }]);
    }

    if (latest.type === "completed") {
      setActiveJob((prev) => prev ? { ...prev, status: "completed", progress: 1.0, plates_found: latest.plates_found ?? prev.plates_found } : prev);
      refreshJobs();
    }

    if (latest.type === "failed") {
      setActiveJob((prev) => prev ? { ...prev, status: "failed", error_message: latest.error || null } : prev);
      refreshJobs();
    }
  }, [messages]);

  const handleSubmit = async () => {
    if (!url) return;
    setSubmitting(true);
    setPlates([]);
    try {
      const res = await createVideoJob({ youtube_url: url, frame_interval_sec: interval });
      const job = res.data.data;
      setActiveJobId(job.id);
      setActiveJob(job);
      setUrl("");
      refreshJobs();
    } finally {
      setSubmitting(false);
    }
  };

  const handleViewJob = async (id: string) => {
    const res = await getVideoJob(id);
    const job = res.data.data;
    setActiveJobId(job.id);
    setActiveJob(job);
    setPlates(job.plates || []);
  };

  const handleDelete = async (id: string) => {
    await deleteVideoJob(id);
    if (activeJobId === id) { setActiveJobId(null); setActiveJob(null); setPlates([]); }
    refreshJobs();
  };

  const statusColor: Record<string, string> = {
    pending: "#94a3b8", downloading: "#f59e0b", processing: "#2563eb", completed: "#16a34a", failed: "#ef4444",
  };

  const statusText: Record<string, string> = {
    pending: "等待中", downloading: "下載中", processing: "分析中", completed: "已完成", failed: "失敗",
  };

  return (
    <div style={{ padding: "2rem" }}>
      <h1>YouTube 影片分析</h1>

      {/* Submit */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "2rem", flexWrap: "wrap", alignItems: "end" }}>
        <div style={{ flex: 3, minWidth: 300 }}>
          <label style={{ display: "block", marginBottom: 4, fontSize: 14, color: "#64748b" }}>YouTube URL</label>
          <input placeholder="https://www.youtube.com/watch?v=..." value={url}
            onChange={(e) => setUrl(e.target.value)}
            style={{ width: "100%", padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4, boxSizing: "border-box" }} />
        </div>
        <div style={{ flex: 1, minWidth: 120 }}>
          <label style={{ display: "block", marginBottom: 4, fontSize: 14, color: "#64748b" }}>抽幀間隔（秒）</label>
          <input type="number" min={0.1} max={30} step={0.1} value={interval}
            onChange={(e) => setInterval_(parseFloat(e.target.value) || 1.0)}
            style={{ width: "100%", padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4, boxSizing: "border-box" }} />
        </div>
        <button onClick={handleSubmit} disabled={!url || submitting}
          style={{ padding: "0.5rem 1.5rem", background: !url || submitting ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: !url || submitting ? "not-allowed" : "pointer", height: 38 }}>
          {submitting ? "提交中..." : "開始分析"}
        </button>
      </div>

      {/* Active Job */}
      {activeJob && (
        <div style={{ padding: "1.5rem", background: "#f8fafc", borderRadius: 8, marginBottom: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h3 style={{ margin: 0 }}>{activeJob.title || "載入中..."}</h3>
              <span style={{ fontSize: 14, color: "#64748b" }}>{activeJob.duration_seconds ? `${Math.floor(activeJob.duration_seconds / 60)}:${String(activeJob.duration_seconds % 60).padStart(2, "0")}` : ""}</span>
            </div>
            <span style={{ color: statusColor[activeJob.status] || "#94a3b8", fontWeight: "bold" }}>
              {statusText[activeJob.status] || activeJob.status}
            </span>
          </div>

          {/* Progress bar */}
          <div style={{ background: "#e2e8f0", borderRadius: 4, height: 8, marginBottom: "0.75rem" }}>
            <div style={{ background: "#2563eb", borderRadius: 4, height: 8, width: `${Math.round(activeJob.progress * 100)}%`, transition: "width 0.3s" }} />
          </div>
          <div style={{ display: "flex", gap: "2rem", fontSize: 14, color: "#64748b" }}>
            <span>進度: {Math.round(activeJob.progress * 100)}%</span>
            <span>幀: {activeJob.processed_frames}/{activeJob.total_frames}</span>
            <span>車牌: {plates.length || activeJob.plates_found}</span>
          </div>

          {activeJob.status === "failed" && activeJob.error_message && (
            <div style={{ marginTop: "0.75rem", padding: "0.5rem", background: "#fef2f2", borderRadius: 4, color: "#ef4444", fontSize: 14 }}>
              {activeJob.error_message}
            </div>
          )}

          {/* Plates found */}
          {plates.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h4>辨識結果</h4>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: "0.5rem" }}>車牌號碼</th>
                    <th style={{ padding: "0.5rem" }}>信心度</th>
                    <th style={{ padding: "0.5rem" }}>影片時間</th>
                  </tr>
                </thead>
                <tbody>
                  {plates.map((p, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #e2e8f0" }}>
                      <td style={{ padding: "0.5rem", fontWeight: "bold" }}>{p.plate_number}</td>
                      <td style={{ padding: "0.5rem" }}>{Math.round(p.confidence * 100)}%</td>
                      <td style={{ padding: "0.5rem" }}>{Math.floor(p.frame_timestamp / 60)}:{String(Math.floor(p.frame_timestamp % 60)).padStart(2, "0")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* History */}
      <h2>歷史任務</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>影片標題</th>
            <th style={{ padding: "0.75rem" }}>狀態</th>
            <th style={{ padding: "0.75rem" }}>車牌數</th>
            <th style={{ padding: "0.75rem" }}>建立時間</th>
            <th style={{ padding: "0.75rem" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem" }}>{j.title || j.youtube_url.substring(0, 40)}</td>
              <td style={{ padding: "0.75rem" }}>
                <span style={{ color: statusColor[j.status] || "#94a3b8" }}>{statusText[j.status] || j.status}</span>
              </td>
              <td style={{ padding: "0.75rem" }}>{j.plates_found}</td>
              <td style={{ padding: "0.75rem" }}>{new Date(j.created_at).toLocaleString()}</td>
              <td style={{ padding: "0.75rem", display: "flex", gap: "0.5rem" }}>
                <button onClick={() => handleViewJob(j.id)}
                  style={{ padding: "0.25rem 0.75rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  查看
                </button>
                <button onClick={() => handleDelete(j.id)}
                  style={{ padding: "0.25rem 0.75rem", background: "#64748b", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  刪除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Update services/frontend/src/App.tsx**

```tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PlateRecords from "./pages/PlateRecords";
import UploadPage from "./pages/UploadPage";
import CameraManage from "./pages/CameraManage";
import YouTubeAnalysis from "./pages/YouTubeAnalysis";

const navStyle = {
  display: "flex",
  gap: "1rem",
  padding: "1rem 2rem",
  background: "#1e293b",
};

const linkStyle = ({ isActive }: { isActive: boolean }) => ({
  color: isActive ? "#60a5fa" : "#94a3b8",
  textDecoration: "none",
  fontWeight: isActive ? ("bold" as const) : ("normal" as const),
});

export default function App() {
  return (
    <BrowserRouter>
      <nav style={navStyle}>
        <NavLink to="/" style={linkStyle}>Dashboard</NavLink>
        <NavLink to="/plates" style={linkStyle}>車牌記錄</NavLink>
        <NavLink to="/upload" style={linkStyle}>上傳辨識</NavLink>
        <NavLink to="/youtube" style={linkStyle}>YouTube 分析</NavLink>
        <NavLink to="/cameras" style={linkStyle}>攝影機管理</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/plates" element={<PlateRecords />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/youtube" element={<YouTubeAnalysis />} />
        <Route path="/cameras" element={<CameraManage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/pages/YouTubeAnalysis.tsx services/frontend/src/App.tsx
git commit -m "feat: YouTube analysis page with progress tracking and live results"
```

---

## Task 11: CI Workflow Update

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Update ci.yml**

Add Video Worker linting in the `lint-api` job, add to `Ruff check` steps:

```yaml
      - name: Ruff check (Video Worker)
        run: ruff check services/video-worker/src/ --output-format=github
```

Add Video Worker Docker build in the `docker-build` job:

```yaml
      - name: Build Video Worker image
        run: docker build -f services/video-worker/Dockerfile -t ocr-video-worker:ci .
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add video-worker to lint and Docker build jobs"
```

---

## Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Add under Architecture, after the Frontend bullet:

```markdown
- **Video Worker** (`services/video-worker/`) — Consumes video job queue, downloads YouTube videos via yt-dlp, extracts frames with OpenCV, pushes into existing queue:frames pipeline
```

Update Data flow:

```markdown
Data flow:
- Camera → MinIO + Redis Queue → OCR → PostgreSQL → API → Frontend
- YouTube URL → API → Redis video queue → Video Worker → yt-dlp + OpenCV → MinIO + Redis frames queue → OCR → PostgreSQL
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Video Worker to CLAUDE.md architecture"
```
