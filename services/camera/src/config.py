import logging
import os

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
