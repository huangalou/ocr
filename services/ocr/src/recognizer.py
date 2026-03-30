import logging

import cv2
import numpy as np
from paddleocr import PaddleOCR

from .plate_filter import is_valid_taiwan_plate, normalize_plate

logger = logging.getLogger(__name__)

_ocr_instance = None


def get_ocr() -> PaddleOCR:
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            show_log=False,
        )
    return _ocr_instance


def recognize_plate(image_bytes: bytes, confidence_threshold: float = 0.6) -> list[dict]:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        logger.warning("Failed to decode image")
        return []

    ocr = get_ocr()
    results = ocr.ocr(img, cls=True)

    plates = []
    for line_group in results:
        if not line_group:
            continue
        for line in line_group:
            bbox, (text, conf) = line
            normalized = normalize_plate(text)
            if is_valid_taiwan_plate(normalized):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                region = {
                    "x": int(min(x_coords)),
                    "y": int(min(y_coords)),
                    "w": int(max(x_coords) - min(x_coords)),
                    "h": int(max(y_coords) - min(y_coords)),
                }
                plates.append({
                    "plate_number": normalized,
                    "confidence": round(float(conf), 4),
                    "plate_region": region,
                })

    return plates
