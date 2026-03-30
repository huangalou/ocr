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
