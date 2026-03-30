# License Plate OCR System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a microservices-based license plate OCR system that captures frames from cameras (RTSP/USB), recognizes Taiwanese license plates via PaddleOCR, and provides a web UI for querying and managing records.

**Architecture:** Four Docker containers (Camera, OCR, API, Frontend) orchestrated by Docker Compose, communicating through Redis queues, storing data in PostgreSQL, and images in MinIO.

**Tech Stack:** Python 3.11, FastAPI, PaddleOCR, OpenCV, SQLAlchemy, Alembic, Redis, PostgreSQL, MinIO, React 18, Vite, TypeScript

---

## Task 1: Project Skeleton & Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `.dockerignore`
- Create: `shared/constants.py`
- Create: `shared/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/josh/ocr
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.env
node_modules/
dist/
.superpowers/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 3: Create .dockerignore**

```dockerignore
__pycache__
*.pyc
node_modules
dist
.git
.env
.superpowers
```

- [ ] **Step 4: Create .env.example**

```env
POSTGRES_USER=ocr
POSTGRES_PASSWORD=ocr_dev_password
POSTGRES_DB=ocr_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_BUCKET=ocr-images

OCR_CONFIDENCE_THRESHOLD=0.6
CAMERA_FRAME_INTERVAL_MS=1000
```

- [ ] **Step 5: Create shared/constants.py**

```python
REDIS_QUEUE_FRAMES = "queue:frames"
REDIS_CHANNEL_PLATES = "channel:plate_recognized"
MINIO_BUCKET = "ocr-images"
```

- [ ] **Step 6: Create shared/__init__.py**

Empty file.

- [ ] **Step 7: Create docker-compose.yml**

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-ocr}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-ocr_dev_password}
      POSTGRES_DB: ${POSTGRES_DB:-ocr_db}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-ocr}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./services/api/src:/app/src
      - ./shared:/app/shared
      - ./migrations:/app/migrations

  ocr:
    build:
      context: .
      dockerfile: services/ocr/Dockerfile
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./services/ocr/src:/app/src
      - ./shared:/app/shared

  camera:
    build:
      context: .
      dockerfile: services/camera/Dockerfile
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      api:
        condition: service_started
    volumes:
      - ./services/camera/src:/app/src
      - ./shared:/app/shared

  frontend:
    build:
      context: services/frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    volumes:
      - ./services/frontend/src:/app/src
    depends_on:
      - api

volumes:
  postgres_data:
  minio_data:
```

- [ ] **Step 8: Copy .env.example to .env**

```bash
cp .env.example .env
```

- [ ] **Step 9: Commit**

```bash
git add .gitignore .dockerignore .env.example docker-compose.yml shared/
git commit -m "feat: project skeleton with docker-compose and shared constants"
```

---

## Task 2: API Service — Database Models & Migrations

**Files:**
- Create: `services/api/Dockerfile`
- Create: `services/api/requirements.txt`
- Create: `services/api/src/__init__.py`
- Create: `services/api/src/database.py`
- Create: `services/api/src/models.py`
- Create: `services/api/alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/` (directory)

- [ ] **Step 1: Create services/api/requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
alembic==1.14.1
redis==5.2.1
boto3==1.36.4
python-multipart==0.0.19
pydantic==2.10.4
```

- [ ] **Step 2: Create services/api/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api/src ./src
COPY shared ./shared
COPY migrations ./migrations
COPY services/api/alembic.ini .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: Create services/api/src/__init__.py**

Empty file.

- [ ] **Step 4: Create services/api/src/database.py**

```python
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{os.environ['POSTGRES_DB']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Create services/api/src/models.py**

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
```

Note: `gin_trgm` index for fuzzy search will be added via a raw SQL migration after initial tables are created.

- [ ] **Step 6: Set up Alembic**

Create `services/api/alembic.ini`:

```ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://%(POSTGRES_USER)s:%(POSTGRES_PASSWORD)s@%(POSTGRES_HOST)s:%(POSTGRES_PORT)s/%(POSTGRES_DB)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 7: Create migrations/env.py**

```python
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import Base
from src.models import Camera, PlateRecord  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

section = config.get_section(config.config_ini_section, {})
for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"):
    val = os.environ.get(key, "")
    section["sqlalchemy.url"] = section.get("sqlalchemy.url", "").replace(f"%({key})s", val)
config.set_section_option(config.config_ini_section, "sqlalchemy.url", section["sqlalchemy.url"])


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Create migrations/script.py.mako**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 9: Generate initial migration**

Run inside the api container after `docker-compose up -d postgres api`:

```bash
docker-compose run --rm api alembic revision --autogenerate -m "initial tables"
```

- [ ] **Step 10: Run migration**

```bash
docker-compose run --rm api alembic upgrade head
```

- [ ] **Step 11: Add trigram extension migration**

Create a manual migration for the gin_trgm index:

```bash
docker-compose run --rm api alembic revision -m "add trigram index for plate_number"
```

Then edit the generated file to contain:

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX idx_plate_like ON plate_records "
        "USING gin (plate_number gin_trgm_ops)"
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_plate_like")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
```

Run: `docker-compose run --rm api alembic upgrade head`

- [ ] **Step 12: Commit**

```bash
git add services/api/ migrations/
git commit -m "feat: API service skeleton with database models and Alembic migrations"
```

---

## Task 3: API Service — Pydantic Schemas & Response Envelope

**Files:**
- Create: `services/api/src/schemas.py`

- [ ] **Step 1: Write test for schemas**

Create `services/api/tests/__init__.py` (empty) and `services/api/tests/test_schemas.py`:

```python
import uuid
from datetime import datetime, timezone

from src.schemas import (
    ApiResponse,
    CameraCreate,
    CameraRead,
    PaginatedResponse,
    PlateRecordRead,
)


def test_camera_create_valid():
    data = CameraCreate(
        name="Entrance Cam",
        source_type="rtsp",
        source_uri="rtsp://192.168.1.100:554/stream",
        frame_interval_ms=1000,
    )
    assert data.name == "Entrance Cam"
    assert data.source_type == "rtsp"


def test_camera_create_defaults():
    data = CameraCreate(
        name="Test",
        source_type="usb",
        source_uri="/dev/video0",
    )
    assert data.frame_interval_ms == 1000


def test_api_response_success():
    resp = ApiResponse(success=True, data={"plate": "ABC-1234"}, error=None)
    assert resp.success is True
    assert resp.data["plate"] == "ABC-1234"


def test_api_response_error():
    resp = ApiResponse(success=False, data=None, error="Not found")
    assert resp.success is False
    assert resp.error == "Not found"


def test_paginated_response():
    resp = PaginatedResponse(
        success=True,
        data=[],
        error=None,
        meta={"total": 0, "page": 1, "page_size": 20},
    )
    assert resp.meta["total"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker-compose run --rm api python -m pytest tests/test_schemas.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.schemas'`

- [ ] **Step 3: Create services/api/src/schemas.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Camera Schemas ---

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


# --- PlateRecord Schemas ---

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


# --- API Response Envelope ---

class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None


class PaginatedResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker-compose run --rm api python -m pytest tests/test_schemas.py -v
```

Expected: all 5 PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/schemas.py services/api/tests/
git commit -m "feat: Pydantic schemas and API response envelope"
```

---

## Task 4: API Service — Camera CRUD Router

**Files:**
- Create: `services/api/src/routers/__init__.py`
- Create: `services/api/src/routers/cameras.py`
- Create: `services/api/tests/test_cameras.py`
- Modify: `services/api/src/main.py`

- [ ] **Step 1: Create services/api/src/main.py (minimal)**

```python
from fastapi import FastAPI

app = FastAPI(title="License Plate OCR API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Write test for camera CRUD**

Create `services/api/tests/conftest.py`:

```python
import os
os.environ.setdefault("POSTGRES_USER", "ocr")
os.environ.setdefault("POSTGRES_PASSWORD", "ocr_dev_password")
os.environ.setdefault("POSTGRES_HOST", "postgres")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "ocr_db")
os.environ.setdefault("REDIS_HOST", "redis")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("MINIO_HOST", "minio")
os.environ.setdefault("MINIO_PORT", "9000")
os.environ.setdefault("MINIO_ROOT_USER", "minioadmin")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "minioadmin")
os.environ.setdefault("MINIO_BUCKET", "ocr-images")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base, get_db
from src.main import app

SQLALCHEMY_TEST_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{os.environ['POSTGRES_DB']}"
)

engine = create_engine(SQLALCHEMY_TEST_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

Create `services/api/tests/test_cameras.py`:

```python
def test_create_camera(client):
    resp = client.post("/api/v1/cameras", json={
        "name": "Entrance",
        "source_type": "rtsp",
        "source_uri": "rtsp://192.168.1.100:554/stream",
        "frame_interval_ms": 500,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Entrance"
    assert body["data"]["is_active"] is False


def test_list_cameras(client):
    client.post("/api/v1/cameras", json={
        "name": "Cam1", "source_type": "usb", "source_uri": "/dev/video0",
    })
    client.post("/api/v1/cameras", json={
        "name": "Cam2", "source_type": "rtsp", "source_uri": "rtsp://x",
    })
    resp = client.get("/api/v1/cameras")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


def test_update_camera(client):
    create = client.post("/api/v1/cameras", json={
        "name": "Old", "source_type": "usb", "source_uri": "/dev/video0",
    })
    cam_id = create.json()["data"]["id"]
    resp = client.put(f"/api/v1/cameras/{cam_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "New"


def test_delete_camera(client):
    create = client.post("/api/v1/cameras", json={
        "name": "ToDelete", "source_type": "usb", "source_uri": "/dev/video0",
    })
    cam_id = create.json()["data"]["id"]
    resp = client.delete(f"/api/v1/cameras/{cam_id}")
    assert resp.status_code == 200
    list_resp = client.get("/api/v1/cameras")
    assert len(list_resp.json()["data"]) == 0


def test_toggle_camera(client):
    create = client.post("/api/v1/cameras", json={
        "name": "Toggler", "source_type": "usb", "source_uri": "/dev/video0",
    })
    cam_id = create.json()["data"]["id"]
    resp = client.post(f"/api/v1/cameras/{cam_id}/toggle")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True
    resp2 = client.post(f"/api/v1/cameras/{cam_id}/toggle")
    assert resp2.json()["data"]["is_active"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
docker-compose run --rm api python -m pytest tests/test_cameras.py -v
```

Expected: FAIL — router not found, 404

- [ ] **Step 4: Create services/api/src/routers/__init__.py**

Empty file.

- [ ] **Step 5: Create services/api/src/routers/cameras.py**

```python
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
def update_camera(
    camera_id: uuid.UUID, body: CameraUpdate, db: Session = Depends(get_db)
):
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
```

- [ ] **Step 6: Register router in main.py**

Update `services/api/src/main.py`:

```python
from fastapi import FastAPI

from .routers import cameras

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
docker-compose run --rm api python -m pytest tests/test_cameras.py -v
```

Expected: all 5 PASS

- [ ] **Step 8: Commit**

```bash
git add services/api/src/ services/api/tests/
git commit -m "feat: camera CRUD API with tests"
```

---

## Task 5: API Service — Plates Router (Query, Detail, Export)

**Files:**
- Create: `services/api/src/routers/plates.py`
- Create: `services/api/tests/test_plates.py`
- Modify: `services/api/src/main.py`

- [ ] **Step 1: Write test**

Create `services/api/tests/test_plates.py`:

```python
import uuid
from datetime import datetime, timezone

from src.models import PlateRecord


def _seed_records(db, count=3):
    records = []
    for i in range(count):
        r = PlateRecord(
            plate_number=f"ABC-{1000 + i}",
            confidence=0.9 - i * 0.1,
            source="camera",
            image_path=f"images/test_{i}.jpg",
            plate_region={"x": 10, "y": 20, "w": 100, "h": 40},
            recognized_at=datetime(2026, 3, 30, 10, i, 0, tzinfo=timezone.utc),
        )
        db.add(r)
        records.append(r)
    db.commit()
    for r in records:
        db.refresh(r)
    return records


def test_list_plates(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 3
    assert body["meta"]["total"] == 3


def test_list_plates_filter_by_plate_number(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates", params={"plate_number": "ABC-1001"})
    assert len(resp.json()["data"]) == 1


def test_list_plates_filter_by_min_confidence(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates", params={"min_confidence": 0.85})
    assert len(resp.json()["data"]) == 1


def test_list_plates_pagination(client, db):
    _seed_records(db, count=5)
    resp = client.get("/api/v1/plates", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["page"] == 1


def test_get_plate_detail(client, db):
    records = _seed_records(db, count=1)
    record_id = str(records[0].id)
    resp = client.get(f"/api/v1/plates/{record_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["plate_number"] == "ABC-1000"


def test_get_plate_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/plates/{fake_id}")
    assert resp.status_code == 404


def test_export_csv(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) == 4  # header + 3 rows


def test_export_json(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates/export", params={"format": "json"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker-compose run --rm api python -m pytest tests/test_plates.py -v
```

Expected: FAIL — 404

- [ ] **Step 3: Create services/api/src/routers/plates.py**

```python
import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PlateRecord
from ..schemas import ApiResponse, PaginatedResponse, PlateRecordRead

router = APIRouter(prefix="/api/v1/plates", tags=["plates"])


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
            content=[
                PlateRecordRead.model_validate(r).model_dump(mode="json")
                for r in records
            ]
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
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plates.csv"},
    )


@router.get("/{record_id}", response_model=ApiResponse)
def get_plate(record_id: uuid.UUID, db: Session = Depends(get_db)):
    record = db.query(PlateRecord).filter(PlateRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return ApiResponse(
        success=True,
        data=PlateRecordRead.model_validate(record).model_dump(mode="json"),
    )
```

- [ ] **Step 4: Register plates router in main.py**

```python
from fastapi import FastAPI

from .routers import cameras, plates

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)
app.include_router(plates.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
docker-compose run --rm api python -m pytest tests/test_plates.py -v
```

Expected: all 8 PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/src/routers/plates.py services/api/tests/test_plates.py services/api/src/main.py
git commit -m "feat: plates query, detail, and export API with tests"
```

---

## Task 6: API Service — Upload Endpoint & WebSocket

**Files:**
- Modify: `services/api/src/routers/plates.py`
- Create: `services/api/src/websocket.py`
- Modify: `services/api/src/main.py`
- Create: `services/api/tests/test_upload.py`

- [ ] **Step 1: Write upload test**

Create `services/api/tests/test_upload.py`:

```python
import io
from unittest.mock import patch, MagicMock


def test_upload_image_pushes_to_queue(client):
    fake_image = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    fake_image.name = "test.png"

    with patch("src.routers.plates.redis_client") as mock_redis, \
         patch("src.routers.plates.minio_client") as mock_minio:
        mock_minio.put_object = MagicMock()
        mock_redis.lpush = MagicMock()

        resp = client.post(
            "/api/v1/plates/upload",
            files={"file": ("test.png", fake_image, "image/png")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert "job_id" in body["data"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker-compose run --rm api python -m pytest tests/test_upload.py -v
```

Expected: FAIL

- [ ] **Step 3: Add upload endpoint to plates.py**

Add these imports to the top of `services/api/src/routers/plates.py`:

```python
import json
import os

import redis as redis_lib
from boto3 import client as boto3_client
```

Add these module-level clients after the imports:

```python
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
```

Add this endpoint (place it **before** the `/{record_id}` route):

```python
@router.post("/upload", response_model=ApiResponse, status_code=202)
async def upload_image(file: UploadFile, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    contents = await file.read()
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    object_key = f"uploads/{job_id}.{ext}"

    minio_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=object_key,
        Body=contents,
        ContentType=file.content_type or "image/jpeg",
    )

    message = json.dumps({
        "job_id": job_id,
        "image_path": object_key,
        "source": "upload",
        "camera_id": None,
    })
    redis_client.lpush("queue:frames", message)

    return ApiResponse(
        success=True,
        data={"job_id": job_id, "image_path": object_key},
    )
```

- [ ] **Step 4: Create services/api/src/websocket.py**

```python
import asyncio
import json
import os

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect


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


manager = PlateWebSocketManager()


async def redis_subscriber():
    redis_url = f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', 6379)}"
    r = aioredis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:plate_recognized")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await manager.broadcast(data)


async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
```

- [ ] **Step 5: Register WebSocket and startup event in main.py**

```python
import asyncio

from fastapi import FastAPI

from .routers import cameras, plates
from .websocket import redis_subscriber, websocket_endpoint

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)
app.include_router(plates.router)
app.add_api_websocket_route("/api/v1/ws/plates", websocket_endpoint)


@app.on_event("startup")
async def startup():
    asyncio.create_task(redis_subscriber())


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
docker-compose run --rm api python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/api/
git commit -m "feat: image upload endpoint and WebSocket notification"
```

---

## Task 7: OCR Service

**Files:**
- Create: `services/ocr/Dockerfile`
- Create: `services/ocr/requirements.txt`
- Create: `services/ocr/src/__init__.py`
- Create: `services/ocr/src/main.py`
- Create: `services/ocr/src/recognizer.py`
- Create: `services/ocr/src/plate_filter.py`
- Create: `services/ocr/src/storage.py`
- Create: `services/ocr/src/db.py`
- Create: `services/ocr/tests/test_plate_filter.py`
- Create: `services/ocr/tests/test_recognizer.py`

- [ ] **Step 1: Create services/ocr/requirements.txt**

```
paddlepaddle==2.6.2
paddleocr==2.9.1
opencv-python-headless==4.10.0.84
redis==5.2.1
psycopg2-binary==2.9.10
sqlalchemy==2.0.36
boto3==1.36.4
numpy==1.26.4
```

- [ ] **Step 2: Create services/ocr/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/ocr/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ocr/src ./src
COPY shared ./shared

CMD ["python", "-m", "src.main"]
```

- [ ] **Step 3: Write plate_filter test**

Create `services/ocr/tests/__init__.py` (empty) and `services/ocr/tests/test_plate_filter.py`:

```python
from src.plate_filter import is_valid_taiwan_plate, normalize_plate


def test_standard_new_format():
    assert is_valid_taiwan_plate("ABC-1234") is True


def test_old_format_two_letters():
    assert is_valid_taiwan_plate("AB-1234") is True


def test_old_format_letters_both_sides():
    assert is_valid_taiwan_plate("AB-12CD") is False  # not a real TW format


def test_motorcycle_format():
    assert is_valid_taiwan_plate("ABC-123") is True


def test_new_6_digit():
    assert is_valid_taiwan_plate("1234-AB") is True


def test_invalid_too_short():
    assert is_valid_taiwan_plate("A-1") is False


def test_invalid_random_text():
    assert is_valid_taiwan_plate("HELLO WORLD") is False


def test_normalize_removes_spaces():
    assert normalize_plate("ABC  1234") == "ABC-1234"


def test_normalize_adds_dash():
    assert normalize_plate("ABC1234") == "ABC-1234"


def test_normalize_already_correct():
    assert normalize_plate("ABC-1234") == "ABC-1234"
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd services/ocr && python -m pytest tests/test_plate_filter.py -v
```

Expected: FAIL — module not found

- [ ] **Step 5: Create services/ocr/src/__init__.py**

Empty file.

- [ ] **Step 6: Create services/ocr/src/plate_filter.py**

```python
import re

# Taiwan license plate patterns:
# New car:        AAA-0000 (3 letters + 4 digits)
# Old car:        AA-0000  (2 letters + 4 digits)
# Motorcycle:     AAA-000  (3 letters + 3 digits)
# New format:     0000-AA  (4 digits + 2 letters)
# Electric:       EAA-0000
TAIWAN_PLATE_PATTERNS = [
    re.compile(r"^[A-Z]{2,4}-\d{3,4}$"),   # letters-digits
    re.compile(r"^\d{4}-[A-Z]{2}$"),         # digits-letters (new format)
]


def normalize_plate(text: str) -> str:
    text = text.upper().strip()
    text = re.sub(r"[^\w]", "", text)  # remove non-alphanumeric

    # Try to insert dash: letters then digits
    m = re.match(r"^([A-Z]{2,4})(\d{3,4})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # digits then letters
    m = re.match(r"^(\d{4})([A-Z]{2})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return text


def is_valid_taiwan_plate(text: str) -> bool:
    normalized = normalize_plate(text)
    return any(p.match(normalized) for p in TAIWAN_PLATE_PATTERNS)
```

- [ ] **Step 7: Run test to verify it passes**

```bash
cd services/ocr && python -m pytest tests/test_plate_filter.py -v
```

Expected: all PASS

- [ ] **Step 8: Create services/ocr/src/storage.py**

```python
import os

from boto3 import client as boto3_client

_client = None


def get_s3_client():
    global _client
    if _client is None:
        _client = boto3_client(
            "s3",
            endpoint_url=f"http://{os.environ['MINIO_HOST']}:{os.environ['MINIO_PORT']}",
            aws_access_key_id=os.environ["MINIO_ROOT_USER"],
            aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        )
    return _client


def upload_image(bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"):
    client = get_s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def download_image(bucket: str, key: str) -> bytes:
    client = get_s3_client()
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()
```

- [ ] **Step 9: Create services/ocr/src/db.py**

```python
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{os.environ['POSTGRES_DB']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def save_plate_record(
    plate_number: str,
    confidence: float,
    source: str,
    image_path: str,
    plate_region: dict | None = None,
    camera_id: str | None = None,
) -> dict:
    session = SessionLocal()
    try:
        record_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        session.execute(
            """
            INSERT INTO plate_records
                (id, camera_id, plate_number, confidence, source, image_path, plate_region, recognized_at, created_at)
            VALUES
                (:id, :camera_id, :plate_number, :confidence, :source, :image_path, :plate_region, :recognized_at, :created_at)
            """,
            {
                "id": record_id,
                "camera_id": uuid.UUID(camera_id) if camera_id else None,
                "plate_number": plate_number,
                "confidence": confidence,
                "source": source,
                "image_path": image_path,
                "plate_region": plate_region,
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
        }
    finally:
        session.close()
```

Note: Uses raw SQL to avoid importing the API service's models. Both services share the same database schema.

- [ ] **Step 10: Create services/ocr/src/recognizer.py**

```python
import logging

import cv2
import numpy as np
from paddleocr import PaddleOCR

from .plate_filter import is_valid_taiwan_plate, normalize_plate

logger = logging.getLogger(__name__)

_ocr_instance = None


def get_ocr() -> PaddleOCR:
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            lang="en",  # plates are alphanumeric
            show_log=False,
        )
    return _ocr_instance


def recognize_plate(image_bytes: bytes, confidence_threshold: float = 0.6) -> list[dict]:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        logger.warning("Failed to decode image")
        return []

    ocr = get_ocr()
    results = ocr.ocr(img, cls=True)

    plates = []
    for line_group in results:
        if not line_group:
            continue
        for line in line_group:
            bbox, (text, conf) = line
            normalized = normalize_plate(text)
            if is_valid_taiwan_plate(normalized):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                region = {
                    "x": int(min(x_coords)),
                    "y": int(min(y_coords)),
                    "w": int(max(x_coords) - min(x_coords)),
                    "h": int(max(y_coords) - min(y_coords)),
                }
                plates.append({
                    "plate_number": normalized,
                    "confidence": round(float(conf), 4),
                    "plate_region": region,
                })

    return plates
```

- [ ] **Step 11: Create services/ocr/src/main.py**

```python
import json
import logging
import os
import time

import redis as redis_lib

from .db import save_plate_record
from .recognizer import recognize_plate
from .storage import download_image, upload_image

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
            record = save_plate_record(
                plate_number=plate["plate_number"],
                confidence=plate["confidence"],
                source=source,
                image_path=image_path,
                plate_region=plate["plate_region"],
                camera_id=camera_id,
            )
            logger.info(f"Saved plate: {plate['plate_number']} (conf={plate['confidence']})")

            r.publish(PUBSUB_CHANNEL, json.dumps(record))


if __name__ == "__main__":
    main()
```

- [ ] **Step 12: Commit**

```bash
git add services/ocr/
git commit -m "feat: OCR service with PaddleOCR, plate filter, and queue consumer"
```

---

## Task 8: Camera Service

**Files:**
- Create: `services/camera/Dockerfile`
- Create: `services/camera/requirements.txt`
- Create: `services/camera/src/__init__.py`
- Create: `services/camera/src/main.py`
- Create: `services/camera/src/capture.py`
- Create: `services/camera/src/config.py`
- Create: `services/camera/src/queue_client.py`

- [ ] **Step 1: Create services/camera/requirements.txt**

```
opencv-python-headless==4.10.0.84
redis==5.2.1
requests==2.32.3
numpy==1.26.4
```

- [ ] **Step 2: Create services/camera/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/camera/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/camera/src ./src
COPY shared ./shared

CMD ["python", "-m", "src.main"]
```

- [ ] **Step 3: Create services/camera/src/__init__.py**

Empty file.

- [ ] **Step 4: Create services/camera/src/config.py**

```python
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")


def fetch_active_cameras() -> list[dict]:
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/cameras", timeout=5)
        resp.raise_for_status()
        body = resp.json()
        return [c for c in body["data"] if c["is_active"]]
    except Exception:
        logger.exception("Failed to fetch cameras from API")
        return []
```

- [ ] **Step 5: Create services/camera/src/queue_client.py**

```python
import json
import os
import uuid

import redis as redis_lib

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_KEY = "queue:frames"

_client = None


def get_redis():
    global _client
    if _client is None:
        _client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    return _client


def push_frame(image_path: str, camera_id: str):
    message = json.dumps({
        "job_id": str(uuid.uuid4()),
        "image_path": image_path,
        "source": "camera",
        "camera_id": camera_id,
    })
    get_redis().lpush(QUEUE_KEY, message)
```

- [ ] **Step 6: Create services/camera/src/capture.py**

```python
import logging
import os
import time
import uuid

import cv2
import numpy as np
from boto3 import client as boto3_client

from .queue_client import push_frame

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


def capture_loop(camera: dict):
    camera_id = camera["id"]
    source_uri = camera["source_uri"]
    interval_ms = camera.get("frame_interval_ms", 1000)
    name = camera["name"]

    logger.info(f"Starting capture for '{name}' ({camera['source_type']}: {source_uri})")

    source = int(source_uri) if camera["source_type"] == "usb" else source_uri
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        logger.error(f"Cannot open camera '{name}' at {source_uri}")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"Failed to read frame from '{name}', retrying in 5s")
                time.sleep(5)
                cap.release()
                cap = cv2.VideoCapture(source)
                continue

            _, buffer = cv2.imencode(".jpg", frame)
            image_bytes = buffer.tobytes()

            object_key = f"frames/{camera_id}/{uuid.uuid4()}.jpg"
            _get_s3().put_object(
                Bucket=MINIO_BUCKET,
                Key=object_key,
                Body=image_bytes,
                ContentType="image/jpeg",
            )

            push_frame(object_key, camera_id)
            logger.debug(f"Pushed frame from '{name}': {object_key}")

            time.sleep(interval_ms / 1000.0)
    finally:
        cap.release()
```

- [ ] **Step 7: Create services/camera/src/main.py**

```python
import logging
import time
import threading

from .config import fetch_active_cameras
from .capture import capture_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("camera-service")

POLL_INTERVAL = 30  # seconds between checking for camera config changes


def main():
    logger.info("Camera service started")
    active_threads: dict[str, threading.Thread] = {}

    while True:
        cameras = fetch_active_cameras()
        active_ids = {c["id"] for c in cameras}

        # Start new cameras
        for cam in cameras:
            cid = cam["id"]
            if cid not in active_threads or not active_threads[cid].is_alive():
                t = threading.Thread(target=capture_loop, args=(cam,), daemon=True)
                t.start()
                active_threads[cid] = t
                logger.info(f"Started thread for camera '{cam['name']}'")

        # Clean up stopped cameras
        for cid in list(active_threads):
            if cid not in active_ids:
                logger.info(f"Camera {cid} no longer active, thread will stop on next iteration")
                del active_threads[cid]

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Commit**

```bash
git add services/camera/
git commit -m "feat: camera service with RTSP/USB capture and frame pushing"
```

---

## Task 9: Frontend — Project Setup & API Client

**Files:**
- Create: `services/frontend/package.json`
- Create: `services/frontend/tsconfig.json`
- Create: `services/frontend/tsconfig.app.json`
- Create: `services/frontend/vite.config.ts`
- Create: `services/frontend/index.html`
- Create: `services/frontend/Dockerfile`
- Create: `services/frontend/src/main.tsx`
- Create: `services/frontend/src/App.tsx`
- Create: `services/frontend/src/api/client.ts`
- Create: `services/frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Scaffold React + Vite project**

```bash
cd /Users/josh/ocr/services
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install axios react-router-dom
```

- [ ] **Step 2: Create services/frontend/Dockerfile**

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 3: Configure Vite proxy**

Update `services/frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://api:8000",
        changeOrigin: true,
      },
      "/api/v1/ws": {
        target: "ws://api:8000",
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 4: Create services/frontend/src/api/client.ts**

```typescript
import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
});

export interface Camera {
  id: string;
  name: string;
  source_type: "rtsp" | "usb";
  source_uri: string;
  is_active: boolean;
  frame_interval_ms: number;
  created_at: string;
  updated_at: string;
}

export interface PlateRecord {
  id: string;
  camera_id: string | null;
  plate_number: string;
  confidence: number;
  source: "camera" | "upload";
  image_path: string;
  plate_region: { x: number; y: number; w: number; h: number } | null;
  recognized_at: string;
  created_at: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  meta: { total: number; page: number; page_size: number };
}

// Cameras
export const listCameras = () => api.get<ApiResponse<Camera[]>>("/cameras");
export const createCamera = (data: Partial<Camera>) =>
  api.post<ApiResponse<Camera>>("/cameras", data);
export const updateCamera = (id: string, data: Partial<Camera>) =>
  api.put<ApiResponse<Camera>>(`/cameras/${id}`, data);
export const deleteCamera = (id: string) =>
  api.delete<ApiResponse<{ deleted: string }>>(`/cameras/${id}`);
export const toggleCamera = (id: string) =>
  api.post<ApiResponse<Camera>>(`/cameras/${id}/toggle`);

// Plates
export const listPlates = (params?: Record<string, string | number>) =>
  api.get<PaginatedResponse<PlateRecord>>("/plates", { params });
export const getPlate = (id: string) =>
  api.get<ApiResponse<PlateRecord>>(`/plates/${id}`);
export const uploadImage = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<ApiResponse<{ job_id: string; image_path: string }>>(
    "/plates/upload",
    form,
  );
};
export const exportPlates = (format: "csv" | "json", params?: Record<string, string>) =>
  api.get(`/plates/export`, { params: { format, ...params }, responseType: format === "csv" ? "blob" : "json" });
```

- [ ] **Step 5: Create services/frontend/src/hooks/useWebSocket.ts**

```typescript
import { useEffect, useRef, useState, useCallback } from "react";
import type { PlateRecord } from "../api/client";

export function usePlateWebSocket() {
  const [latestPlate, setLatestPlate] = useState<PlateRecord | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/plates`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLatestPlate(data);
    };

    ws.onclose = () => {
      setTimeout(connect, 3000);
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return latestPlate;
}
```

- [ ] **Step 6: Commit**

```bash
git add services/frontend/
git commit -m "feat: frontend project setup with API client and WebSocket hook"
```

---

## Task 10: Frontend — Dashboard Page

**Files:**
- Modify: `services/frontend/src/App.tsx`
- Create: `services/frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Create services/frontend/src/pages/Dashboard.tsx**

```tsx
import { useEffect, useState } from "react";
import { listPlates, listCameras } from "../api/client";
import type { PlateRecord, Camera } from "../api/client";
import { usePlateWebSocket } from "../hooks/useWebSocket";

export default function Dashboard() {
  const [records, setRecords] = useState<PlateRecord[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [todayCount, setTodayCount] = useState(0);
  const latestPlate = usePlateWebSocket();

  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    listPlates({ start_date: today, page_size: 10, sort_by: "recognized_at", sort_order: "desc" }).then((res) => {
      setRecords(res.data.data);
      setTodayCount(res.data.meta.total);
    });
    listCameras().then((res) => setCameras(res.data.data));
  }, []);

  useEffect(() => {
    if (latestPlate) {
      setRecords((prev) => [latestPlate, ...prev].slice(0, 10));
      setTodayCount((prev) => prev + 1);
    }
  }, [latestPlate]);

  const onlineCameras = cameras.filter((c) => c.is_active).length;
  const avgConfidence =
    records.length > 0
      ? Math.round((records.reduce((sum, r) => sum + r.confidence, 0) / records.length) * 100)
      : 0;

  return (
    <div style={{ padding: "2rem" }}>
      <h1>Dashboard</h1>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem" }}>
        <div style={{ flex: 1, padding: "1.5rem", background: "#f0f9ff", borderRadius: 8 }}>
          <div style={{ fontSize: 32, fontWeight: "bold", color: "#2563eb" }}>{todayCount}</div>
          <div style={{ color: "#64748b" }}>今日辨識</div>
        </div>
        <div style={{ flex: 1, padding: "1.5rem", background: "#f0fdf4", borderRadius: 8 }}>
          <div style={{ fontSize: 32, fontWeight: "bold", color: "#16a34a" }}>{onlineCameras}</div>
          <div style={{ color: "#64748b" }}>攝影機在線</div>
        </div>
        <div style={{ flex: 1, padding: "1.5rem", background: "#fffbeb", borderRadius: 8 }}>
          <div style={{ fontSize: 32, fontWeight: "bold", color: "#d97706" }}>{avgConfidence}%</div>
          <div style={{ color: "#64748b" }}>平均信心度</div>
        </div>
      </div>

      <h2>最近辨識記錄</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>車牌號碼</th>
            <th style={{ padding: "0.75rem" }}>來源</th>
            <th style={{ padding: "0.75rem" }}>信心度</th>
            <th style={{ padding: "0.75rem" }}>時間</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem", fontWeight: "bold" }}>{r.plate_number}</td>
              <td style={{ padding: "0.75rem" }}>{r.source === "camera" ? `攝影機` : "手動上傳"}</td>
              <td style={{ padding: "0.75rem" }}>{Math.round(r.confidence * 100)}%</td>
              <td style={{ padding: "0.75rem" }}>{new Date(r.recognized_at).toLocaleTimeString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Update App.tsx with routing**

```tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";

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
        <NavLink to="/cameras" style={linkStyle}>攝影機管理</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/plates" element={<div style={{ padding: "2rem" }}>TODO: PlateRecords</div>} />
        <Route path="/upload" element={<div style={{ padding: "2rem" }}>TODO: Upload</div>} />
        <Route path="/cameras" element={<div style={{ padding: "2rem" }}>TODO: Cameras</div>} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/
git commit -m "feat: Dashboard page with stats cards and live record list"
```

---

## Task 11: Frontend — Plate Records Page

**Files:**
- Create: `services/frontend/src/pages/PlateRecords.tsx`
- Modify: `services/frontend/src/App.tsx`

- [ ] **Step 1: Create services/frontend/src/pages/PlateRecords.tsx**

```tsx
import { useEffect, useState } from "react";
import { listPlates, exportPlates } from "../api/client";
import type { PlateRecord } from "../api/client";

export default function PlateRecords() {
  const [records, setRecords] = useState<PlateRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const pageSize = 20;

  const fetchRecords = () => {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (search) params.plate_number = search;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    listPlates(params).then((res) => {
      setRecords(res.data.data);
      setTotal(res.data.meta.total);
    });
  };

  useEffect(() => { fetchRecords(); }, [page]);

  const handleSearch = () => { setPage(1); fetchRecords(); };

  const handleExport = async (format: "csv" | "json") => {
    const params: Record<string, string> = {};
    if (search) params.plate_number = search;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const res = await exportPlates(format, params);
    const blob = res.data instanceof Blob ? res.data : new Blob([JSON.stringify(res.data)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `plates.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div style={{ padding: "2rem" }}>
      <h1>車牌記錄查詢</h1>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <input placeholder="搜尋車牌號碼..." value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4, minWidth: 200 }} />
        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
          style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
          style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
        <button onClick={handleSearch} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>
          搜尋
        </button>
        <button onClick={() => handleExport("csv")} style={{ padding: "0.5rem 1rem", background: "#16a34a", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>
          匯出 CSV
        </button>
        <button onClick={() => handleExport("json")} style={{ padding: "0.5rem 1rem", background: "#d97706", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>
          匯出 JSON
        </button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>車牌號碼</th>
            <th style={{ padding: "0.75rem" }}>來源</th>
            <th style={{ padding: "0.75rem" }}>信心度</th>
            <th style={{ padding: "0.75rem" }}>辨識時間</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem", fontWeight: "bold" }}>{r.plate_number}</td>
              <td style={{ padding: "0.75rem" }}>{r.source === "camera" ? "攝影機" : "手動上傳"}</td>
              <td style={{ padding: "0.75rem" }}>{Math.round(r.confidence * 100)}%</td>
              <td style={{ padding: "0.75rem" }}>{new Date(r.recognized_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: "flex", justifyContent: "center", gap: "0.5rem", marginTop: "1rem" }}>
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}
          style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: 4, cursor: "pointer" }}>
          上一頁
        </button>
        <span style={{ padding: "0.5rem", lineHeight: "2" }}>第 {page} / {totalPages} 頁（共 {total} 筆）</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}
          style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: 4, cursor: "pointer" }}>
          下一頁
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update App.tsx — replace placeholder**

Replace the plates route in `App.tsx`:

```tsx
import PlateRecords from "./pages/PlateRecords";
```

Change the route:

```tsx
<Route path="/plates" element={<PlateRecords />} />
```

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/
git commit -m "feat: plate records page with search, filter, pagination, and export"
```

---

## Task 12: Frontend — Upload Page

**Files:**
- Create: `services/frontend/src/pages/UploadPage.tsx`
- Modify: `services/frontend/src/App.tsx`

- [ ] **Step 1: Create services/frontend/src/pages/UploadPage.tsx**

```tsx
import { useState, useCallback } from "react";
import { uploadImage } from "../api/client";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<{ job_id: string; image_path: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = (f: File) => {
    setFile(f);
    setResult(null);
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(f);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadImage(file);
      setResult(res.data.data);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ padding: "2rem", maxWidth: 600 }}>
      <h1>上傳圖片辨識</h1>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById("file-input")?.click()}
        style={{
          border: `2px dashed ${dragOver ? "#2563eb" : "#d1d5db"}`,
          borderRadius: 8,
          padding: "3rem",
          textAlign: "center",
          cursor: "pointer",
          background: dragOver ? "#eff6ff" : "transparent",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ fontSize: 48, marginBottom: "0.5rem" }}>📷</div>
        <p style={{ color: "#64748b" }}>拖拽圖片至此 或 點擊選擇檔案</p>
        <p style={{ color: "#94a3b8", fontSize: 14 }}>支援 JPG, PNG, BMP</p>
        <input
          id="file-input"
          type="file"
          accept="image/jpeg,image/png,image/bmp"
          style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
      </div>

      {preview && (
        <div style={{ marginBottom: "1.5rem" }}>
          <img src={preview} alt="preview" style={{ maxWidth: "100%", borderRadius: 8 }} />
          <p style={{ color: "#64748b", marginTop: "0.5rem" }}>{file?.name}</p>
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        style={{
          padding: "0.75rem 2rem",
          background: !file || uploading ? "#94a3b8" : "#2563eb",
          color: "white",
          border: "none",
          borderRadius: 4,
          cursor: !file || uploading ? "not-allowed" : "pointer",
          fontSize: 16,
        }}
      >
        {uploading ? "上傳中..." : "開始辨識"}
      </button>

      {result && (
        <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#f0fdf4", borderRadius: 8 }}>
          <p style={{ color: "#16a34a", fontWeight: "bold" }}>已送出辨識請求</p>
          <p style={{ color: "#64748b", fontSize: 14 }}>Job ID: {result.job_id}</p>
          <p style={{ color: "#64748b", fontSize: 14 }}>辨識結果將顯示在 Dashboard 即時列表中</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update App.tsx — replace placeholder**

Add import and update route:

```tsx
import UploadPage from "./pages/UploadPage";
```

```tsx
<Route path="/upload" element={<UploadPage />} />
```

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/
git commit -m "feat: upload page with drag-and-drop and preview"
```

---

## Task 13: Frontend — Camera Management Page

**Files:**
- Create: `services/frontend/src/pages/CameraManage.tsx`
- Modify: `services/frontend/src/App.tsx`

- [ ] **Step 1: Create services/frontend/src/pages/CameraManage.tsx**

```tsx
import { useEffect, useState } from "react";
import { listCameras, createCamera, updateCamera, deleteCamera, toggleCamera } from "../api/client";
import type { Camera } from "../api/client";

interface FormData {
  name: string;
  source_type: "rtsp" | "usb";
  source_uri: string;
  frame_interval_ms: number;
}

const emptyForm: FormData = { name: "", source_type: "rtsp", source_uri: "", frame_interval_ms: 1000 };

export default function CameraManage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const refresh = () => listCameras().then((res) => setCameras(res.data.data));

  useEffect(() => { refresh(); }, []);

  const handleSubmit = async () => {
    if (editingId) {
      await updateCamera(editingId, form);
    } else {
      await createCamera(form);
    }
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
    refresh();
  };

  const handleEdit = (cam: Camera) => {
    setForm({
      name: cam.name,
      source_type: cam.source_type,
      source_uri: cam.source_uri,
      frame_interval_ms: cam.frame_interval_ms,
    });
    setEditingId(cam.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    await deleteCamera(id);
    refresh();
  };

  const handleToggle = async (id: string) => {
    await toggleCamera(id);
    refresh();
  };

  return (
    <div style={{ padding: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h1>攝影機管理</h1>
        <button
          onClick={() => { setForm(emptyForm); setEditingId(null); setShowForm(!showForm); }}
          style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}
        >
          {showForm ? "取消" : "+ 新增攝影機"}
        </button>
      </div>

      {showForm && (
        <div style={{ padding: "1.5rem", background: "#f8fafc", borderRadius: 8, marginBottom: "1.5rem" }}>
          <h3>{editingId ? "編輯攝影機" : "新增攝影機"}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxWidth: 400 }}>
            <input placeholder="名稱" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
            <select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value as "rtsp" | "usb" })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }}>
              <option value="rtsp">RTSP</option>
              <option value="usb">USB</option>
            </select>
            <input placeholder="來源 URI（RTSP URL 或裝置編號）" value={form.source_uri}
              onChange={(e) => setForm({ ...form, source_uri: e.target.value })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
            <input type="number" placeholder="抽幀間隔 (ms)" value={form.frame_interval_ms}
              onChange={(e) => setForm({ ...form, frame_interval_ms: parseInt(e.target.value) || 1000 })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
            <button onClick={handleSubmit}
              style={{ padding: "0.5rem 1rem", background: "#16a34a", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>
              {editingId ? "更新" : "建立"}
            </button>
          </div>
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>名稱</th>
            <th style={{ padding: "0.75rem" }}>類型</th>
            <th style={{ padding: "0.75rem" }}>來源</th>
            <th style={{ padding: "0.75rem" }}>狀態</th>
            <th style={{ padding: "0.75rem" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {cameras.map((cam) => (
            <tr key={cam.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem" }}>{cam.name}</td>
              <td style={{ padding: "0.75rem" }}>{cam.source_type.toUpperCase()}</td>
              <td style={{ padding: "0.75rem", fontSize: 14, color: "#64748b" }}>{cam.source_uri}</td>
              <td style={{ padding: "0.75rem" }}>
                <span style={{ color: cam.is_active ? "#16a34a" : "#ef4444" }}>
                  {cam.is_active ? "● 啟用" : "● 停用"}
                </span>
              </td>
              <td style={{ padding: "0.75rem", display: "flex", gap: "0.5rem" }}>
                <button onClick={() => handleToggle(cam.id)}
                  style={{ padding: "0.25rem 0.75rem", background: cam.is_active ? "#ef4444" : "#16a34a", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  {cam.is_active ? "停用" : "啟用"}
                </button>
                <button onClick={() => handleEdit(cam)}
                  style={{ padding: "0.25rem 0.75rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  編輯
                </button>
                <button onClick={() => handleDelete(cam.id)}
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

- [ ] **Step 2: Update App.tsx — final routing**

Final `App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PlateRecords from "./pages/PlateRecords";
import UploadPage from "./pages/UploadPage";
import CameraManage from "./pages/CameraManage";

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
        <NavLink to="/cameras" style={linkStyle}>攝影機管理</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/plates" element={<PlateRecords />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/cameras" element={<CameraManage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/
git commit -m "feat: camera management page with CRUD and toggle"
```

---

## Task 14: Production Docker Compose

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `services/frontend/Dockerfile.prod`
- Create: `services/frontend/nginx.conf`

- [ ] **Step 1: Create services/frontend/nginx.conf**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Create services/frontend/Dockerfile.prod**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 3: Create docker-compose.prod.yml**

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 512M
    restart: unless-stopped

  ocr:
    build:
      context: .
      dockerfile: services/ocr/Dockerfile
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2G
    restart: unless-stopped

  camera:
    build:
      context: .
      dockerfile: services/camera/Dockerfile
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      api:
        condition: service_started
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 512M
    restart: unless-stopped

  frontend:
    build:
      context: services/frontend
      dockerfile: Dockerfile.prod
    ports:
      - "80:80"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  minio_data:
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml services/frontend/Dockerfile.prod services/frontend/nginx.conf
git commit -m "feat: production Docker Compose with Nginx and resource limits"
```

---

## Task 15: Integration Smoke Test

**Files:**
- Create: `scripts/smoke-test.sh`

- [ ] **Step 1: Create scripts/smoke-test.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

echo "=== Smoke Test ==="

echo -n "Health check... "
curl -sf "$BASE_URL/health" | grep -q '"ok"' && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "Create camera... "
CAM=$(curl -sf -X POST "$BASE_URL/api/v1/cameras" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Cam","source_type":"usb","source_uri":"0"}')
CAM_ID=$(echo "$CAM" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "PASS (id=$CAM_ID)"

echo -n "List cameras... "
curl -sf "$BASE_URL/api/v1/cameras" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['data'])>=1" && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "Toggle camera... "
curl -sf -X POST "$BASE_URL/api/v1/cameras/$CAM_ID/toggle" | python3 -c "import sys,json; assert json.load(sys.stdin)['data']['is_active']==True" && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "List plates (empty)... "
curl -sf "$BASE_URL/api/v1/plates" | python3 -c "import sys,json; assert json.load(sys.stdin)['meta']['total']==0" && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "Delete camera... "
curl -sf -X DELETE "$BASE_URL/api/v1/cameras/$CAM_ID" | grep -q '"success": true\|"success":true' && echo "PASS" || { echo "FAIL"; exit 1; }

echo "=== All smoke tests passed ==="
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/smoke-test.sh
```

- [ ] **Step 3: Run smoke test**

```bash
docker-compose up -d
sleep 10
./scripts/smoke-test.sh
```

Expected: All 6 checks PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "test: add integration smoke test script"
```

---

## Task 16: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with project commands and architecture**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

License plate OCR system — microservices architecture with Docker Compose.

## Quick Start

```bash
cp .env.example .env
docker-compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

## Commands

```bash
# Run all services
docker-compose up --build

# Run DB migrations
docker-compose run --rm api alembic upgrade head

# Create new migration
docker-compose run --rm api alembic revision --autogenerate -m "description"

# Run API tests
docker-compose run --rm api python -m pytest tests/ -v

# Run OCR service tests
cd services/ocr && python -m pytest tests/ -v

# Run smoke tests
./scripts/smoke-test.sh

# Production deploy
docker-compose -f docker-compose.prod.yml up --build -d

# Frontend dev (standalone with hot reload)
cd services/frontend && npm run dev
```

## Architecture

Four microservices communicating via Redis queues, sharing PostgreSQL and MinIO:

- **Camera Service** (`services/camera/`) — OpenCV captures frames from RTSP/USB cameras, uploads to MinIO, pushes job to Redis queue
- **OCR Service** (`services/ocr/`) — Consumes Redis queue, downloads image from MinIO, runs PaddleOCR, validates Taiwan plate format, saves to PostgreSQL, publishes result to Redis pub/sub
- **API Service** (`services/api/`) — FastAPI REST API for CRUD, queries, export. Subscribes to Redis pub/sub and pushes to WebSocket clients
- **Frontend** (`services/frontend/`) — React + Vite + TypeScript SPA with 4 pages: Dashboard, PlateRecords, UploadPage, CameraManage

Data flow: Camera → MinIO + Redis Queue → OCR → PostgreSQL → API → Frontend

## Key Files

- `shared/constants.py` — Redis keys and channel names shared across services
- `services/ocr/src/plate_filter.py` — Taiwan license plate format validation and normalization
- `services/api/src/models.py` — SQLAlchemy models (Camera, PlateRecord)
- `services/api/src/schemas.py` — Pydantic request/response schemas
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with project architecture and commands"
```
