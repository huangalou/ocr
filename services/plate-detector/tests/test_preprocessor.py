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
