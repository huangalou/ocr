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
        "format": "best[height<=720]/best",
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
        "format": "best[height<=720]/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]


def should_stream(duration_seconds: int) -> bool:
    return duration_seconds > VIDEO_STREAM_THRESHOLD_SEC
