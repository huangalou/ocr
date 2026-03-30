import json
import logging
import os
import time

import cv2
import numpy as np
import redis as redis_lib

from .detector import detect_plates
from .preprocessor import crop_and_enhance
from .storage import download_image, upload_image, MINIO_BUCKET
from .tracker import JobTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("plate-detector")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

QUEUE_VIDEO_FRAMES = "queue:video_frames"
QUEUE_PLATE_CROPS = "queue:plate_crops"

JOB_TIMEOUT_SEC = 60


def _flush_job(tracker: JobTracker, job_id: str, r: redis_lib.Redis):
    """Select best frames for each tracked plate, preprocess, upload, and push to OCR queue."""
    best_frames = tracker.get_best_frames(job_id)
    logger.info(f"Job {job_id}: flushing {len(best_frames)} tracked plates")

    for frame_info in best_frames:
        cropped = crop_and_enhance(frame_info["image"], frame_info["bbox"])

        _, buffer = cv2.imencode(".jpg", cropped)
        crop_bytes = buffer.tobytes()

        crop_key = f"videos/{job_id}/crop_track{frame_info['track_id']:03d}.jpg"
        upload_image(MINIO_BUCKET, crop_key, crop_bytes)

        msg = frame_info["message"]
        crop_msg = json.dumps({
            "job_id": msg.get("job_id", job_id),
            "image_path": crop_key,
            "source": "youtube",
            "camera_id": None,
            "video_job_id": job_id,
            "frame_timestamp": frame_info["frame_timestamp"],
        })
        r.lpush(QUEUE_PLATE_CROPS, crop_msg)

    tracker.cleanup(job_id)


def main():
    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    tracker = JobTracker()

    logger.info("Plate detector started, waiting for video frames...")

    while True:
        result = r.brpop(QUEUE_VIDEO_FRAMES, timeout=5)

        # Check for timed-out jobs even when queue is empty
        if result is None:
            _check_timeouts(tracker, r)
            continue

        _, raw = result
        message = json.loads(raw)

        # Handle sentinel message
        if message.get("type") == "end_of_frames":
            job_id = message["video_job_id"]
            logger.info(f"Job {job_id}: received end_of_frames (total={message.get('total_frames')})")
            if tracker.has_pending_data(job_id):
                _flush_job(tracker, job_id, r)
            continue

        job_id = message.get("video_job_id", "unknown")
        image_path = message["image_path"]

        try:
            image_bytes = download_image(MINIO_BUCKET, image_path)
        except Exception:
            logger.exception(f"Failed to download image: {image_path}")
            continue

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            logger.warning(f"Failed to decode image: {image_path}")
            continue

        detections = detect_plates(image)

        if not detections:
            continue

        for i, det in enumerate(detections):
            track_id = hash((job_id, det["bbox"][0], det["bbox"][1])) % 100000 + i
            tracker.store_candidate(
                job_id=job_id,
                track_id=track_id,
                confidence=det["confidence"],
                bbox=det["bbox"],
                image=image,
                frame_timestamp=message.get("frame_timestamp", 0.0),
                message=message,
            )

        logger.info(f"Job {job_id}: {len(detections)} plates detected in {image_path}")

        _check_timeouts(tracker, r)


def _check_timeouts(tracker: JobTracker, r: redis_lib.Redis):
    """Flush jobs that have been inactive for longer than JOB_TIMEOUT_SEC."""
    now = time.monotonic()
    for job_id in list(tracker._tracks.keys()):
        last = tracker.get_last_activity(job_id)
        if last > 0 and (now - last) > JOB_TIMEOUT_SEC:
            logger.warning(f"Job {job_id}: timeout after {JOB_TIMEOUT_SEC}s inactivity, flushing")
            _flush_job(tracker, job_id, r)


if __name__ == "__main__":
    main()
