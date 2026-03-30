import json
import os
import uuid

import redis as redis_lib

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_KEY = "queue:frames"

_client = None


def get_redis():
    global _client
    if _client is None:
        _client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    return _client


def push_frame(image_path: str, camera_id: str):
    message = json.dumps({
        "job_id": str(uuid.uuid4()),
        "image_path": image_path,
        "source": "camera",
        "camera_id": camera_id,
    })
    get_redis().lpush(QUEUE_KEY, message)
