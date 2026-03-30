import asyncio

from fastapi import FastAPI

from .routers import cameras, plates
from .websocket import redis_subscriber, websocket_endpoint

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)
app.include_router(plates.router)
app.add_api_websocket_route("/api/v1/ws/plates", websocket_endpoint)


@app.on_event("startup")
async def startup():
    asyncio.create_task(redis_subscriber())


@app.get("/health")
def health():
    return {"status": "ok"}
