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
FRAMES_QUEUE_KEY = "queue:video_frames"

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

            # Send sentinel to plate-detector
            sentinel = json.dumps({
                "video_job_id": job_id,
                "type": "end_of_frames",
                "total_frames": extracted,
            })
            r.lpush(FRAMES_QUEUE_KEY, sentinel)

        except Exception as e:
            logger.exception(f"Video job {job_id} failed")
            mark_failed(job_id, str(e))


if __name__ == "__main__":
    main()
