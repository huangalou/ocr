import logging
import math
import os

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
