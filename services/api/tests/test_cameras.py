def test_create_camera(client):
    resp = client.post("/api/v1/cameras", json={
        "name": "Entrance", "source_type": "rtsp",
        "source_uri": "rtsp://192.168.1.100:554/stream", "frame_interval_ms": 500,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Entrance"
    assert body["data"]["is_active"] is False


def test_list_cameras(client):
    client.post("/api/v1/cameras", json={"name": "Cam1", "source_type": "usb", "source_uri": "/dev/video0"})
    client.post("/api/v1/cameras", json={"name": "Cam2", "source_type": "rtsp", "source_uri": "rtsp://x"})
    resp = client.get("/api/v1/cameras")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


def test_update_camera(client):
    create = client.post("/api/v1/cameras", json={"name": "Old", "source_type": "usb", "source_uri": "/dev/video0"})
    cam_id = create.json()["data"]["id"]
    resp = client.put(f"/api/v1/cameras/{cam_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "New"


def test_delete_camera(client):
    create = client.post("/api/v1/cameras", json={"name": "ToDelete", "source_type": "usb", "source_uri": "/dev/video0"})
    cam_id = create.json()["data"]["id"]
    resp = client.delete(f"/api/v1/cameras/{cam_id}")
    assert resp.status_code == 200
    list_resp = client.get("/api/v1/cameras")
    assert len(list_resp.json()["data"]) == 0


def test_toggle_camera(client):
    create = client.post("/api/v1/cameras", json={"name": "Toggler", "source_type": "usb", "source_uri": "/dev/video0"})
    cam_id = create.json()["data"]["id"]
    resp = client.post(f"/api/v1/cameras/{cam_id}/toggle")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True
    resp2 = client.post(f"/api/v1/cameras/{cam_id}/toggle")
    assert resp2.json()["data"]["is_active"] is False
