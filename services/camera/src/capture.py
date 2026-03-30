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
