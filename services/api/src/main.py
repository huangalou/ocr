import asyncio

from fastapi import FastAPI

from .routers import cameras, plates, videos
from .websocket import redis_subscriber, video_progress_subscriber, websocket_endpoint, video_websocket_endpoint

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)
app.include_router(plates.router)
app.include_router(videos.router)
app.add_api_websocket_route("/api/v1/ws/plates", websocket_endpoint)
app.add_api_websocket_route("/api/v1/ws/videos/{job_id}", video_websocket_endpoint)


@app.on_event("startup")
async def startup():
    asyncio.create_task(redis_subscriber())
    asyncio.create_task(video_progress_subscriber())


@app.get("/health")
def health():
    return {"status": "ok"}
