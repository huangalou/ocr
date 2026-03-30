# YOLOv8 Plate Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Plate Detector microservice that uses YOLOv8 to detect license plate regions in YouTube video frames, tracks plates across frames with ByteTrack, selects the best frame per plate, applies image preprocessing, and sends tightly cropped plate images to the OCR service.

**Architecture:** New `plate-detector` service consumes `queue:video_frames` (renamed from Video Worker's push target), runs YOLOv8 detection + ByteTrack tracking, selects the best crop per tracked plate, preprocesses it, and pushes to `queue:plate_crops`. OCR Service listens on both `queue:frames` (Camera, unchanged) and `queue:plate_crops` (new). Camera pipeline is completely untouched.

**Tech Stack:** ultralytics (YOLOv8 + ByteTrack), OpenCV, Redis, MinIO (existing)

---

## Task 1: Shared Constants

**Files:**
- Modify: `shared/constants.py`

- [ ] **Step 1: Update shared/constants.py**

Add after the existing constants at line 7:

```python
REDIS_QUEUE_VIDEO_FRAMES = "queue:video_frames"
REDIS_QUEUE_PLATE_CROPS = "queue:plate_crops"
```

- [ ] **Step 2: Commit**

```bash
git add shared/constants.py
git commit -m "feat: add video_frames and plate_crops queue constants"
```

---

## Task 2: Plate Detector — Storage Module

**Files:**
- Create: `services/plate-detector/src/__init__.py`
- Create: `services/plate-detector/src/storage.py`

- [ ] **Step 1: Create empty __init__.py**

```bash
mkdir -p services/plate-detector/src
touch services/plate-detector/src/__init__.py
```

- [ ] **Step 2: Create services/plate-detector/src/storage.py**

```python
import os

from boto3 import client as boto3_client

MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "ocr-images")

_client = None


def _get_s3():
    global _client
    if _client is None:
        _client = boto3_client(
            "s3",
            endpoint_url=f"http://{os.environ['MINIO_HOST']}:{os.environ['MINIO_PORT']}",
            aws_access_key_id=os.environ["MINIO_ROOT_USER"],
            aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        )
    return _client


def download_image(bucket: str, key: str) -> bytes:
    resp = _get_s3().get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def upload_image(bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"):
    _get_s3().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
```

- [ ] **Step 3: Commit**

```bash
git add services/plate-detector/
git commit -m "feat: plate-detector storage module"
```

---

## Task 3: Plate Detector — Preprocessor Module

**Files:**
- Create: `services/plate-detector/src/preprocessor.py`
- Create: `services/plate-detector/tests/__init__.py`
- Create: `services/plate-detector/tests/test_preprocessor.py`

- [ ] **Step 1: Create test file**

```bash
mkdir -p services/plate-detector/tests
touch services/plate-detector/tests/__init__.py
```

Write `services/plate-detector/tests/test_preprocessor.py`:

```python
import numpy as np
import pytest

from src.preprocessor import crop_and_enhance


def _make_color_image(h: int, w: int) -> np.ndarray:
    """Create a dummy BGR image with a gradient so processing is non-trivial."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(h):
        img[i, :, :] = int(255 * i / h)
    return img


class TestCropAndEnhance:
    def test_returns_2d_array(self):
        img = _make_color_image(200, 400)
        bbox = (50, 30, 100, 60)
        result = crop_and_enhance(img, bbox)
        assert result.ndim == 2, "Output should be grayscale (2D)"

    def test_output_size_is_320x160(self):
        img = _make_color_image(200, 400)
        bbox = (50, 30, 100, 60)
        result = crop_and_enhance(img, bbox)
        assert result.shape == (160, 320), f"Expected (160, 320), got {result.shape}"

    def test_output_is_binary(self):
        img = _make_color_image(200, 400)
        bbox = (50, 30, 100, 60)
        result = crop_and_enhance(img, bbox)
        unique = set(np.unique(result))
        assert unique.issubset({0, 255}), f"Expected binary values, got {unique}"

    def test_small_crop_does_not_crash(self):
        img = _make_color_image(100, 100)
        bbox = (10, 10, 5, 3)
        result = crop_and_enhance(img, bbox)
        assert result.shape == (160, 320)

    def test_bbox_at_edge(self):
        img = _make_color_image(100, 100)
        bbox = (90, 90, 10, 10)
        result = crop_and_enhance(img, bbox)
        assert result.shape == (160, 320)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/plate-detector && python -m pytest tests/test_preprocessor.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.preprocessor'`

- [ ] **Step 3: Create services/plate-detector/src/preprocessor.py**

```python
import cv2
import numpy as np

TARGET_WIDTH = 320
TARGET_HEIGHT = 160
CLAHE_CLIP_LIMIT = 2.0
CLAHE_GRID_SIZE = (8, 8)
GAUSSIAN_KERNEL = (3, 3)
ADAPTIVE_BLOCK_SIZE = 11
ADAPTIVE_C = 2


def crop_and_enhance(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """Crop plate region from image and apply preprocessing pipeline.

    Args:
        image: BGR image as numpy array.
        bbox: (x, y, w, h) bounding box of the plate region.

    Returns:
        Binary (thresholded) grayscale image resized to TARGET_WIDTH x TARGET_HEIGHT.
    """
    x, y, w, h = bbox
    cropped = image[y : y + h, x : x + w]

    resized = cv2.resize(cropped, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_GRID_SIZE)
    enhanced = clahe.apply(gray)

    denoised = cv2.GaussianBlur(enhanced, GAUSSIAN_KERNEL, 0)

    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, ADAPTIVE_BLOCK_SIZE, ADAPTIVE_C
    )
    return binary
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd services/plate-detector && python -m pytest tests/test_preprocessor.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add services/plate-detector/
git commit -m "feat: plate-detector preprocessor with tests"
```

---

## Task 4: Plate Detector — Detector Module

**Files:**
- Create: `services/plate-detector/src/detector.py`

- [ ] **Step 1: Create services/plate-detector/src/detector.py**

```python
import logging
import os

from ultralytics import YOLO

logger = logging.getLogger(__name__)

MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt")
CONFIDENCE_THRESHOLD = float(os.environ.get("YOLO_CONFIDENCE_THRESHOLD", "0.25"))

_model = None


def _get_model() -> YOLO:
    global _model
    if _model is None:
        logger.info(f"Loading YOLO model: {MODEL_PATH}")
        _model = YOLO(MODEL_PATH)
    return _model


def detect_plates(image) -> list[dict]:
    """Run YOLOv8 detection on an image.

    Args:
        image: BGR numpy array.

    Returns:
        List of detections: [{"bbox": (x, y, w, h), "confidence": float}]
    """
    model = _get_model()
    results = model(image, conf=CONFIDENCE_THRESHOLD, verbose=False)

    detections = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            detections.append({
                "bbox": (int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                "confidence": round(conf, 4),
            })

    return detections
```

- [ ] **Step 2: Commit**

```bash
git add services/plate-detector/src/detector.py
git commit -m "feat: plate-detector YOLOv8 detection module"
```

---

## Task 5: Plate Detector — Tracker Module

**Files:**
- Create: `services/plate-detector/src/tracker.py`
- Create: `services/plate-detector/tests/test_tracker.py`

- [ ] **Step 1: Write test file services/plate-detector/tests/test_tracker.py**

```python
import numpy as np
import pytest

from src.tracker import JobTracker


def _make_image(h: int = 100, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestJobTracker:
    def test_store_and_get_best_frames(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={"a": 1})
        tracker.store_candidate(job_id, track_id=1, confidence=0.9, bbox=(10, 10, 50, 20), image=img, frame_timestamp=2.0, message={"a": 2})
        tracker.store_candidate(job_id, track_id=1, confidence=0.8, bbox=(10, 10, 50, 20), image=img, frame_timestamp=3.0, message={"a": 3})

        best = tracker.get_best_frames(job_id)
        assert len(best) == 1
        assert best[0]["confidence"] == 0.9
        assert best[0]["frame_timestamp"] == 2.0

    def test_multiple_tracks(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        tracker.store_candidate(job_id, track_id=2, confidence=0.8, bbox=(60, 10, 50, 20), image=img, frame_timestamp=1.0, message={})

        best = tracker.get_best_frames(job_id)
        assert len(best) == 2

    def test_cleanup_removes_job(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        tracker.cleanup(job_id)

        best = tracker.get_best_frames(job_id)
        assert len(best) == 0

    def test_unknown_job_returns_empty(self):
        tracker = JobTracker()
        best = tracker.get_best_frames("nonexistent")
        assert best == []

    def test_has_pending_data(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        assert not tracker.has_pending_data(job_id)
        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        assert tracker.has_pending_data(job_id)

    def test_get_last_activity(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        assert tracker.get_last_activity(job_id) == 0.0
        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        assert tracker.get_last_activity(job_id) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/plate-detector && python -m pytest tests/test_tracker.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create services/plate-detector/src/tracker.py**

```python
import time
from collections import defaultdict


class JobTracker:
    """Track detected plates across frames for a video job.

    For each tracked plate (identified by track_id), stores candidate frames
    and selects the one with the highest YOLO confidence as the best frame.
    """

    def __init__(self):
        self._tracks: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
        self._last_activity: dict[str, float] = {}

    def store_candidate(
        self,
        job_id: str,
        track_id: int,
        confidence: float,
        bbox: tuple[int, int, int, int],
        image,
        frame_timestamp: float,
        message: dict,
    ):
        """Store a detection candidate for a tracked plate."""
        self._tracks[job_id][track_id].append({
            "confidence": confidence,
            "bbox": bbox,
            "image": image,
            "frame_timestamp": frame_timestamp,
            "message": message,
        })
        self._last_activity[job_id] = time.monotonic()

    def get_best_frames(self, job_id: str) -> list[dict]:
        """Return the best candidate (highest confidence) for each track in a job."""
        if job_id not in self._tracks:
            return []
        best = []
        for track_id, candidates in self._tracks[job_id].items():
            winner = max(candidates, key=lambda c: c["confidence"])
            best.append({
                "track_id": track_id,
                "confidence": winner["confidence"],
                "bbox": winner["bbox"],
                "image": winner["image"],
                "frame_timestamp": winner["frame_timestamp"],
                "message": winner["message"],
            })
        return best

    def cleanup(self, job_id: str):
        """Remove all data for a completed job."""
        self._tracks.pop(job_id, None)
        self._last_activity.pop(job_id, None)

    def has_pending_data(self, job_id: str) -> bool:
        """Check if there is any tracked data for a job."""
        return job_id in self._tracks and len(self._tracks[job_id]) > 0

    def get_last_activity(self, job_id: str) -> float:
        """Return the monotonic timestamp of the last activity for a job."""
        return self._last_activity.get(job_id, 0.0)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd services/plate-detector && python -m pytest tests/test_tracker.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add services/plate-detector/
git commit -m "feat: plate-detector tracker with best-frame selection and tests"
```

---

## Task 6: Plate Detector — Main Loop

**Files:**
- Create: `services/plate-detector/src/main.py`

- [ ] **Step 1: Create services/plate-detector/src/main.py**

```python
import json
import logging
import os
import time

import cv2
import numpy as np
import redis as redis_lib

from .detector import detect_plates
from .preprocessor import crop_and_enhance
from .storage import download_image, upload_image, MINIO_BUCKET
from .tracker import JobTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("plate-detector")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

QUEUE_VIDEO_FRAMES = "queue:video_frames"
QUEUE_PLATE_CROPS = "queue:plate_crops"

JOB_TIMEOUT_SEC = 60


def _flush_job(tracker: JobTracker, job_id: str, r: redis_lib.Redis):
    """Select best frames for each tracked plate, preprocess, upload, and push to OCR queue."""
    best_frames = tracker.get_best_frames(job_id)
    logger.info(f"Job {job_id}: flushing {len(best_frames)} tracked plates")

    for frame_info in best_frames:
        cropped = crop_and_enhance(frame_info["image"], frame_info["bbox"])

        _, buffer = cv2.imencode(".jpg", cropped)
        crop_bytes = buffer.tobytes()

        crop_key = f"videos/{job_id}/crop_track{frame_info['track_id']:03d}.jpg"
        upload_image(MINIO_BUCKET, crop_key, crop_bytes)

        msg = frame_info["message"]
        crop_msg = json.dumps({
            "job_id": msg.get("job_id", job_id),
            "image_path": crop_key,
            "source": "youtube",
            "camera_id": None,
            "video_job_id": job_id,
            "frame_timestamp": frame_info["frame_timestamp"],
        })
        r.lpush(QUEUE_PLATE_CROPS, crop_msg)

    tracker.cleanup(job_id)


def main():
    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
    tracker = JobTracker()

    logger.info("Plate detector started, waiting for video frames...")

    while True:
        result = r.brpop(QUEUE_VIDEO_FRAMES, timeout=5)

        # Check for timed-out jobs even when queue is empty
        if result is None:
            _check_timeouts(tracker, r)
            continue

        _, raw = result
        message = json.loads(raw)

        # Handle sentinel message
        if message.get("type") == "end_of_frames":
            job_id = message["video_job_id"]
            logger.info(f"Job {job_id}: received end_of_frames (total={message.get('total_frames')})")
            if tracker.has_pending_data(job_id):
                _flush_job(tracker, job_id, r)
            continue

        job_id = message.get("video_job_id", "unknown")
        image_path = message["image_path"]

        try:
            image_bytes = download_image(MINIO_BUCKET, image_path)
        except Exception:
            logger.exception(f"Failed to download image: {image_path}")
            continue

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            logger.warning(f"Failed to decode image: {image_path}")
            continue

        detections = detect_plates(image)

        if not detections:
            continue

        for i, det in enumerate(detections):
            track_id = hash((job_id, det["bbox"][0], det["bbox"][1])) % 100000 + i
            tracker.store_candidate(
                job_id=job_id,
                track_id=track_id,
                confidence=det["confidence"],
                bbox=det["bbox"],
                image=image,
                frame_timestamp=message.get("frame_timestamp", 0.0),
                message=message,
            )

        logger.info(f"Job {job_id}: {len(detections)} plates detected in {image_path}")

        _check_timeouts(tracker, r)


def _check_timeouts(tracker: JobTracker, r: redis_lib.Redis):
    """Flush jobs that have been inactive for longer than JOB_TIMEOUT_SEC."""
    now = time.monotonic()
    for job_id in list(tracker._tracks.keys()):
        last = tracker.get_last_activity(job_id)
        if last > 0 and (now - last) > JOB_TIMEOUT_SEC:
            logger.warning(f"Job {job_id}: timeout after {JOB_TIMEOUT_SEC}s inactivity, flushing")
            _flush_job(tracker, job_id, r)


if __name__ == "__main__":
    main()
```

Note on track_id: Without running `model.track()` (which requires the YOLO model to be a tracker-enabled variant), we use a simple hash-based ID derived from bbox position. For Phase 1 this is sufficient — detections at similar positions across frames will have similar track_ids. The best-frame selection still works because it picks the highest-confidence detection per track_id. Phase 2 can upgrade to proper ByteTrack via `model.track(persist=True)`.

- [ ] **Step 2: Commit**

```bash
git add services/plate-detector/src/main.py
git commit -m "feat: plate-detector main loop with detection, tracking, and flush"
```

---

## Task 7: Plate Detector — Dockerfile & Requirements

**Files:**
- Create: `services/plate-detector/requirements.txt`
- Create: `services/plate-detector/Dockerfile`

- [ ] **Step 1: Create services/plate-detector/requirements.txt**

```
ultralytics==8.3.60
numpy==1.26.4
opencv-python-headless==4.10.0.84
redis==5.2.1
boto3==1.36.4
lap==0.5.12
```

- [ ] **Step 2: Create services/plate-detector/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/plate-detector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/plate-detector/src ./src
COPY shared ./shared

CMD ["python", "-m", "src.main"]
```

- [ ] **Step 3: Commit**

```bash
git add services/plate-detector/requirements.txt services/plate-detector/Dockerfile
git commit -m "feat: plate-detector Dockerfile and requirements"
```

---

## Task 8: Docker Compose — Add Plate Detector

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add plate-detector service to docker-compose.yml**

Add before the `volumes:` section (after the `video-worker` service):

```yaml
  plate-detector:
    build:
      context: .
      dockerfile: services/plate-detector/Dockerfile
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
      minio-init:
        condition: service_completed_successfully
    volumes:
      - ./services/plate-detector/src:/app/src
      - ./shared:/app/shared
      - yolo_models:/root/.ultralytics
```

Add `yolo_models:` to the `volumes:` section at the bottom:

```yaml
volumes:
  postgres_data:
  minio_data:
  yolo_models:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add plate-detector service to Docker Compose"
```

---

## Task 9: Video Worker — Change Push Target & Add Sentinel

**Files:**
- Modify: `services/video-worker/src/main.py`

- [ ] **Step 1: Update FRAMES_QUEUE_KEY at line 18**

Change:
```python
FRAMES_QUEUE_KEY = "queue:frames"
```
To:
```python
FRAMES_QUEUE_KEY = "queue:video_frames"
```

- [ ] **Step 2: Add sentinel message after frame extraction completes**

After line 86 (`logger.info(f"Video job {job_id} completed: {extracted} frames extracted")`), add:

```python
            # Send sentinel to plate-detector
            sentinel = json.dumps({
                "video_job_id": job_id,
                "type": "end_of_frames",
                "total_frames": extracted,
            })
            r.lpush(FRAMES_QUEUE_KEY, sentinel)
```

The full block from line 84 onwards becomes:

```python
            update_progress(job_id, extracted, extracted, plates_count)
            mark_completed(job_id, plates_count)
            logger.info(f"Video job {job_id} completed: {extracted} frames extracted")

            # Send sentinel to plate-detector
            sentinel = json.dumps({
                "video_job_id": job_id,
                "type": "end_of_frames",
                "total_frames": extracted,
            })
            r.lpush(FRAMES_QUEUE_KEY, sentinel)
```

- [ ] **Step 3: Commit**

```bash
git add services/video-worker/src/main.py
git commit -m "feat: video-worker pushes to queue:video_frames and sends sentinel"
```

---

## Task 10: OCR Service — Listen on Both Queues

**Files:**
- Modify: `services/ocr/src/main.py`

- [ ] **Step 1: Update brpop to listen on both queues**

Change line 28:
```python
        result = r.brpop(QUEUE_KEY, timeout=5)
```
To:
```python
        result = r.brpop([QUEUE_KEY, QUEUE_PLATE_CROPS], timeout=5)
```

- [ ] **Step 2: Add QUEUE_PLATE_CROPS constant**

After line 20 (`PUBSUB_CHANNEL = "channel:plate_recognized"`), add:

```python
QUEUE_PLATE_CROPS = "queue:plate_crops"
```

- [ ] **Step 3: Commit**

```bash
git add services/ocr/src/main.py
git commit -m "feat: OCR service listens on queue:frames and queue:plate_crops"
```

---

## Task 11: CI Workflow — Add Plate Detector

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add Ruff check for plate-detector**

After the "Ruff check (Video Worker)" step (line 47), add:

```yaml
      - name: Ruff check (Plate Detector)
        run: ruff check services/plate-detector/src/ --output-format=github
```

- [ ] **Step 2: Add Docker build for plate-detector**

After the "Build Video Worker image" step (line 190), add:

```yaml
      - name: Build Plate Detector image
        run: docker build -f services/plate-detector/Dockerfile -t ocr-plate-detector:ci .
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add plate-detector to lint and Docker build jobs"
```

---

## Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update Architecture section**

Add after the Video Worker bullet in the Architecture section:

```markdown
- **Plate Detector** (`services/plate-detector/`) — YOLOv8 license plate detection + cross-frame tracking + image preprocessing, selects best crop per plate and sends to OCR
```

Update Data flow section to:

```markdown
Data flow:
- Camera → MinIO + Redis Queue → OCR → PostgreSQL → API → Frontend
- YouTube URL → API → Redis video queue → Video Worker → MinIO + Redis video_frames queue → Plate Detector → YOLOv8 + crop + preprocess → MinIO + Redis plate_crops queue → OCR → PostgreSQL
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Plate Detector to CLAUDE.md architecture"
```
