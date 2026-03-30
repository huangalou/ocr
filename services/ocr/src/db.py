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
            text(
                "INSERT INTO plate_records "
                "(id, camera_id, plate_number, confidence, source, image_path, plate_region, recognized_at, created_at) "
                "VALUES "
                "(:id, :camera_id, :plate_number, :confidence, :source, :image_path, CAST(:plate_region AS jsonb), :recognized_at, :created_at)"
            ),
            {
                "id": record_id,
                "camera_id": uuid.UUID(camera_id) if camera_id else None,
                "plate_number": plate_number,
                "confidence": confidence,
                "source": source,
                "image_path": image_path,
                "plate_region": str(plate_region).replace("'", '"') if plate_region else None,
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
