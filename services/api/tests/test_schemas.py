from src.schemas import (
    ApiResponse, CameraCreate, CameraRead, PaginatedResponse, PlateRecordRead,
)


def test_camera_create_valid():
    data = CameraCreate(
        name="Entrance Cam", source_type="rtsp",
        source_uri="rtsp://192.168.1.100:554/stream", frame_interval_ms=1000,
    )
    assert data.name == "Entrance Cam"
    assert data.source_type == "rtsp"


def test_camera_create_defaults():
    data = CameraCreate(name="Test", source_type="usb", source_uri="/dev/video0")
    assert data.frame_interval_ms == 1000


def test_api_response_success():
    resp = ApiResponse(success=True, data={"plate": "ABC-1234"}, error=None)
    assert resp.success is True
    assert resp.data["plate"] == "ABC-1234"


def test_api_response_error():
    resp = ApiResponse(success=False, data=None, error="Not found")
    assert resp.success is False


def test_paginated_response():
    resp = PaginatedResponse(success=True, data=[], error=None, meta={"total": 0, "page": 1, "page_size": 20})
    assert resp.meta["total"] == 0
