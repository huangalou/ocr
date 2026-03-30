# YOLOv8 Plate Detector Design Spec

## Problem

The current OCR pipeline feeds full video frames directly to PaddleOCR (a general-purpose text OCR). For YouTube video frames, license plates are small, compressed, and blurry — PaddleOCR cannot reliably detect or read them.

## Solution

Add a dedicated **Plate Detector** microservice between Video Worker and OCR Service. It uses YOLOv8 for plate region detection, ByteTrack for cross-frame tracking, selects the best frame per tracked plate, and applies image preprocessing before sending tightly cropped plate images to OCR.

## Architecture

### Data Flow

```
YouTube URL → API → queue:video_jobs → Video Worker
  → yt-dlp download → OpenCV extract frames
  → MinIO + queue:video_frames (changed from queue:frames)

queue:video_frames → Plate Detector (NEW)
  → YOLOv8 detect plate regions
  → ByteTrack cross-frame tracking
  → Select best frame per tracked plate (highest YOLO confidence)
  → Crop + preprocess (resize/grayscale/CLAHE/denoise/binarize)
  → Upload crop to MinIO → queue:plate_crops (NEW)

queue:plate_crops → OCR Service
  → PaddleOCR recognize text on cropped plate image
  → plate_filter validate Taiwan format
  → Write to DB + publish Redis pub/sub

Camera → queue:frames → OCR Service (UNCHANGED)
```

### What's New

- 1 new microservice: `plate-detector`
- 2 new Redis queues: `queue:video_frames`, `queue:plate_crops`
- Video Worker push target changed: `queue:frames` → `queue:video_frames`
- OCR Service listens on both `queue:frames` and `queue:plate_crops`

### What's Unchanged

- Camera → `queue:frames` → OCR pipeline untouched
- API Service, Frontend, DB schema — no changes
- docker-compose.yml — only adds new service, no changes to existing services

## Plate Detector Service

### File Structure

```
services/plate-detector/
├── Dockerfile
├── requirements.txt
└── src/
    ├── __init__.py
    ├── main.py          # Main loop: consume queue:video_frames
    ├── detector.py      # YOLOv8 detection
    ├── tracker.py       # ByteTrack cross-frame tracking + best frame selection
    ├── preprocessor.py  # Crop + image preprocessing
    └── storage.py       # MinIO upload/download
```

### Main Loop (main.py)

```
while True:
    msg = brpop("queue:video_frames")

    if msg.type == "end_of_frames":
        # Sentinel: trigger vote + push for this job
        best_frames = tracker.get_best_frames(msg.video_job_id)
        for frame_info in best_frames:
            cropped = preprocessor.crop_and_enhance(frame_info.image, frame_info.bbox)
            crop_key = upload_to_minio(cropped, job_id, track_id)
            push_to_queue("queue:plate_crops", {
                job_id, image_path: crop_key, source: "youtube",
                video_job_id, frame_timestamp
            })
        tracker.cleanup(msg.video_job_id)
        continue

    image = download_from_minio(msg.image_path)
    detections = detector.detect(image)

    for det in detections:
        track_id = tracker.update(msg.video_job_id, det, msg.frame_timestamp)
        tracker.store_candidate(track_id, det, image, msg)

    # Timeout fallback: if no frames for 60s, treat job as complete
```

### YOLOv8 Detection (detector.py)

- Model: Pre-trained license plate detection model (YOLOv8n fine-tuned on plates)
- Source: Ultralytics Hub — auto-downloaded on first run
- Future: Fine-tune with collected Taiwan plate data
- Returns: list of `{bbox: [x, y, w, h], confidence: float}` per frame

### ByteTrack Tracking (tracker.py)

- Uses `ultralytics` built-in ByteTrack via `model.track()`
- Assigns persistent `track_id` to each detected plate across frames
- Per track_id, stores all candidate frames with metadata:
  - bbox, YOLO confidence, image bytes, frame_timestamp, original message
- On job completion, selects the candidate with **highest YOLO confidence** per track_id
- Memory: in-memory dict keyed by video_job_id. Cleaned up after each job.
  - Typical: <50 tracks per job, ~50KB per candidate crop = <3MB per job

### Image Preprocessing (preprocessor.py)

Applied to the cropped plate region before sending to OCR:

1. **Crop** — Extract bbox region from full frame
2. **Resize** — Scale to 320x160 using cubic interpolation
3. **Grayscale** — Convert BGR to grayscale
4. **CLAHE** — Contrast Limited Adaptive Histogram Equalization (clipLimit=2.0, tileGridSize=8x8)
5. **Denoise** — Gaussian blur (3x3 kernel)
6. **Binarize** — Adaptive Gaussian threshold (blockSize=11, C=2)

```python
def crop_and_enhance(image, bbox):
    x, y, w, h = bbox
    cropped = image[y:y+h, x:x+w]
    resized = cv2.resize(cropped, (320, 160), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)
    binary = cv2.adaptiveThreshold(denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    return binary
```

## Changes to Existing Services

### Video Worker (2 changes)

1. **Push target**: `FRAMES_QUEUE_KEY` changed from `"queue:frames"` to `"queue:video_frames"`
2. **Sentinel message**: After all frames extracted, push:
   ```json
   {"video_job_id": "xxx", "type": "end_of_frames", "total_frames": 22}
   ```

### OCR Service (1 change)

`brpop` listens on both queues:
```python
result = r.brpop(["queue:frames", "queue:plate_crops"], timeout=5)
```

Message format from `queue:plate_crops` is identical to `queue:frames`. No other changes needed.

### shared/constants.py (2 new constants)

```python
REDIS_QUEUE_VIDEO_FRAMES = "queue:video_frames"
REDIS_QUEUE_PLATE_CROPS = "queue:plate_crops"
```

## Dependencies & Docker

### requirements.txt

```
ultralytics==8.3.60
numpy==1.26.4
opencv-python-headless==4.10.0.84
redis==5.2.1
boto3==1.36.4
lap==0.5.12
```

### Dockerfile

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

### Docker Compose Addition

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
  volumes:
    - ./services/plate-detector/src:/app/src
    - ./shared:/app/shared
    - yolo_models:/root/.ultralytics
```

Volume `yolo_models` persists downloaded YOLO model weights across container restarts.

### Container Size

- ultralytics + PyTorch CPU: ~800MB
- Other packages: ~100MB
- Total: ~1GB image (smaller than OCR container with PaddlePaddle ~1.2GB)

## Error Handling

| Scenario | Handling |
|----------|----------|
| YOLO detects no plates in a frame | Normal — skip silently |
| ByteTrack loses track | New track_id assigned; OCR `is_duplicate_plate` deduplicates |
| Sentinel message lost | Timeout: if no frames for 60s, treat job as complete |
| Image download fails | Log + skip, don't break the job |
| Video Worker crashes before sentinel | Timeout fallback covers this |
| PaddleOCR can't read cropped plate | Normal flow — "No plates found" |

## Performance

- YOLOv8n inference: ~15ms/frame (CPU)
- ByteTrack tracking: ~1ms
- Preprocessing: ~5ms
- Total per frame: ~20ms
- 213s video (22 frames @ 10s interval): <1 second total detection time

## YOLO Model Strategy

1. **Phase 1 (now)**: Use pre-trained plate detection model from Ultralytics Hub
2. **Phase 2 (later)**: Collect real data from system usage, fine-tune on Taiwan plates
