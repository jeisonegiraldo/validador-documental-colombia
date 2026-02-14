from __future__ import annotations

import logging
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

JPEG_QUALITY = 92


def enhance_image(image_bytes: bytes) -> bytes:
    """Apply enhancement pipeline to a document image.

    Steps: auto-crop, contrast (CLAHE), denoise, sharpen.
    Falls back to original if any step fails.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Could not decode image, returning original")
            return image_bytes

        img = _auto_crop(img)
        img = _enhance_contrast(img)
        img = _denoise(img)
        img = _sharpen(img)

        return _encode_jpeg(img)

    except Exception as e:
        logger.warning("Image enhancement failed, returning original: %s", e)
        return image_bytes


def _auto_crop(img: np.ndarray) -> np.ndarray:
    """Detect document edges and apply perspective warp."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(largest) / (img.shape[0] * img.shape[1])
        if area_ratio < 0.2:
            return img

        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            rect = _order_points(pts)
            warped = _four_point_transform(img, rect)
            return warped

        return img
    except Exception as e:
        logger.debug("Auto-crop failed: %s", e)
        return img


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def _four_point_transform(img: np.ndarray, rect: np.ndarray) -> np.ndarray:
    """Apply perspective transform to obtain a top-down view."""
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, matrix, (max_width, max_height))


def _enhance_contrast(img: np.ndarray) -> np.ndarray:
    """Apply CLAHE to the L channel in LAB color space."""
    try:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    except Exception as e:
        logger.debug("Contrast enhancement failed: %s", e)
        return img


def _denoise(img: np.ndarray) -> np.ndarray:
    """Apply fast non-local means denoising."""
    try:
        return cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)
    except Exception as e:
        logger.debug("Denoise failed: %s", e)
        return img


def _sharpen(img: np.ndarray) -> np.ndarray:
    """Apply unsharp mask sharpening."""
    try:
        blurred = cv2.GaussianBlur(img, (0, 0), 3)
        return cv2.addWeighted(img, 1.5, blurred, -0.5, 0)
    except Exception as e:
        logger.debug("Sharpen failed: %s", e)
        return img


def _encode_jpeg(img: np.ndarray) -> bytes:
    """Encode image as JPEG bytes."""
    success, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not success:
        raise RuntimeError("Failed to encode JPEG")
    return buffer.tobytes()
