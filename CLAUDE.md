# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

License plate OCR system — microservices architecture with Docker Compose.
Recognizes Taiwanese license plates from camera streams (RTSP/USB) and manual uploads using PaddleOCR.

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

# Run API tests (requires postgres + redis running)
docker-compose run --rm api python -m pytest tests/ -v

# Run OCR plate_filter unit tests (no Docker needed)
cd services/ocr && python -m pytest tests/test_plate_filter.py -v

# Run smoke tests (requires API running)
./scripts/smoke-test.sh

# Production deploy
docker-compose -f docker-compose.prod.yml up --build -d

# Frontend dev (standalone with hot reload)
cd services/frontend && npm run dev
```

## Architecture

Five microservices communicating via Redis queues, sharing PostgreSQL and MinIO:

- **Camera Service** (`services/camera/`) — OpenCV captures frames from RTSP/USB cameras, uploads to MinIO, pushes job to Redis queue
- **OCR Service** (`services/ocr/`) — Consumes Redis queue, downloads image from MinIO, runs PaddleOCR, validates Taiwan plate format, saves to PostgreSQL, publishes result to Redis pub/sub
- **API Service** (`services/api/`) — FastAPI REST API for CRUD, queries, export. Subscribes to Redis pub/sub and pushes to WebSocket clients
- **Frontend** (`services/frontend/`) — React + Vite + TypeScript SPA with 4 pages: Dashboard, PlateRecords, UploadPage, CameraManage
- **Video Worker** (`services/video-worker/`) — Consumes video job queue, downloads YouTube videos via yt-dlp, extracts frames with OpenCV, pushes into existing queue:frames pipeline

Data flow:
- Camera → MinIO + Redis Queue → OCR → PostgreSQL → API → Frontend
- YouTube URL → API → Redis video queue → Video Worker → yt-dlp + OpenCV → MinIO + Redis frames queue → OCR → PostgreSQL

## Key Files

- `shared/constants.py` — Redis keys and channel names shared across services
- `services/ocr/src/plate_filter.py` — Taiwan license plate format validation and normalization
- `services/api/src/models.py` — SQLAlchemy models (Camera, PlateRecord)
- `services/api/src/schemas.py` — Pydantic request/response schemas
