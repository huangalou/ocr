import uuid
from datetime import datetime, timezone
from src.models import PlateRecord


def _seed_records(db, count=3):
    records = []
    for i in range(count):
        r = PlateRecord(
            plate_number=f"ABC-{1000 + i}", confidence=0.9 - i * 0.1,
            source="camera", image_path=f"images/test_{i}.jpg",
            plate_region={"x": 10, "y": 20, "w": 100, "h": 40},
            recognized_at=datetime(2026, 3, 30, 10, i, 0, tzinfo=timezone.utc),
        )
        db.add(r)
        records.append(r)
    db.commit()
    for r in records:
        db.refresh(r)
    return records


def test_list_plates(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 3
    assert body["meta"]["total"] == 3


def test_list_plates_filter_by_plate_number(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates", params={"plate_number": "ABC-1001"})
    assert len(resp.json()["data"]) == 1


def test_list_plates_filter_by_min_confidence(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates", params={"min_confidence": 0.85})
    assert len(resp.json()["data"]) == 1


def test_list_plates_pagination(client, db):
    _seed_records(db, count=5)
    resp = client.get("/api/v1/plates", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5


def test_get_plate_detail(client, db):
    records = _seed_records(db, count=1)
    record_id = str(records[0].id)
    resp = client.get(f"/api/v1/plates/{record_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["plate_number"] == "ABC-1000"


def test_get_plate_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/plates/{fake_id}")
    assert resp.status_code == 404


def test_export_csv(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) == 4


def test_export_json(client, db):
    _seed_records(db)
    resp = client.get("/api/v1/plates/export", params={"format": "json"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
