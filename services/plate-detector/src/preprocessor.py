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
