import asyncio

from fastapi import FastAPI

from .routers import cameras, plates

app = FastAPI(title="License Plate OCR API", version="1.0.0")

app.include_router(cameras.router)
app.include_router(plates.router)


@app.on_event("startup")
async def startup():
    pass


@app.get("/health")
def health():
    return {"status": "ok"}
