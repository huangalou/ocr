import asyncio
import json
import os
from collections import defaultdict

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

REDIS_URL = f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', 6379)}"


class PlateWebSocketManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, data: dict):
        message = json.dumps(data)
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                self._connections.remove(ws)


class VideoWebSocketManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[job_id].append(ws)

    def disconnect(self, job_id: str, ws: WebSocket):
        if job_id in self._connections:
            self._connections[job_id].remove(ws)
            if not self._connections[job_id]:
                del self._connections[job_id]

    async def send_to_job(self, job_id: str, data: dict):
        message = json.dumps(data)
        for ws in list(self._connections.get(job_id, [])):
            try:
                await ws.send_text(message)
            except Exception:
                self._connections[job_id].remove(ws)


plate_manager = PlateWebSocketManager()
video_manager = VideoWebSocketManager()


async def redis_subscriber():
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:plate_recognized")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await plate_manager.broadcast(data)
            video_job_id = data.get("video_job_id")
            if video_job_id:
                await video_manager.send_to_job(video_job_id, {
                    "type": "plate_found",
                    "plate_number": data["plate_number"],
                    "confidence": data["confidence"],
                    "frame_timestamp": data.get("frame_timestamp"),
                })


async def video_progress_subscriber():
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:video_progress")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            job_id = data.get("job_id")
            if job_id:
                await video_manager.send_to_job(job_id, data)


async def websocket_endpoint(ws: WebSocket):
    await plate_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        plate_manager.disconnect(ws)


async def video_websocket_endpoint(ws: WebSocket, job_id: str):
    await video_manager.connect(job_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        video_manager.disconnect(job_id, ws)
