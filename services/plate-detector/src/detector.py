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
