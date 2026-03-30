import asyncio
import json
import os

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect


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


manager = PlateWebSocketManager()


async def redis_subscriber():
    redis_url = f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', 6379)}"
    r = aioredis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:plate_recognized")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await manager.broadcast(data)


async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
