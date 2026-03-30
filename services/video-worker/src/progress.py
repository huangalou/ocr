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
