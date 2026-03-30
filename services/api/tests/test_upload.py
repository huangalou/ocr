import io
from unittest.mock import patch, MagicMock


def test_upload_image_pushes_to_queue(client):
    fake_image = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    fake_image.name = "test.png"

    with patch("src.routers.plates.redis_client") as mock_redis, \
         patch("src.routers.plates.minio_client") as mock_minio:
        mock_minio.put_object = MagicMock()
        mock_redis.lpush = MagicMock()

        resp = client.post(
            "/api/v1/plates/upload",
            files={"file": ("test.png", fake_image, "image/png")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert "job_id" in body["data"]
