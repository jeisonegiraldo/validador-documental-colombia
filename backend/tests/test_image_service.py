"""Tests for the image enhancement service."""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import patch

from app.services.image_service import enhance_image, _enhance_contrast, _denoise, _sharpen


def _create_test_image(width: int = 200, height: int = 300) -> bytes:
    """Create a simple test image as JPEG bytes."""
    import cv2
    img = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


class TestEnhanceImage:

    def test_returns_bytes(self):
        image_bytes = _create_test_image()
        result = enhance_image(image_bytes)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_invalid_bytes_returns_original(self):
        bad_bytes = b"not an image"
        result = enhance_image(bad_bytes)
        assert result == bad_bytes

    def test_output_is_valid_jpeg(self):
        image_bytes = _create_test_image()
        result = enhance_image(image_bytes)
        # JPEG magic bytes
        assert result[:2] == b"\xff\xd8"

    def test_empty_image_returns_original(self):
        result = enhance_image(b"")
        assert result == b""


class TestContrastEnhancement:

    def test_clahe_applies(self):
        import cv2
        img = np.random.randint(50, 150, (100, 100, 3), dtype=np.uint8)
        result = _enhance_contrast(img)
        assert result.shape == img.shape
        # CLAHE should change the image
        assert not np.array_equal(result, img)


class TestDenoise:

    def test_denoise_applies(self):
        # Create a noisy image
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = _denoise(img)
        assert result.shape == img.shape


class TestSharpen:

    def test_sharpen_applies(self):
        img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        result = _sharpen(img)
        assert result.shape == img.shape
