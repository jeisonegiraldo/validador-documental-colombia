from __future__ import annotations

import logging
from typing import Tuple

import httpx

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")
DOWNLOAD_TIMEOUT = 30.0


async def fetch_file(url: str) -> Tuple[bytes, str]:
    """Download a file from a URL and return (content_bytes, mime_type).

    Raises ValueError for validation failures, httpx errors for network issues.
    """
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0].strip()

        if not any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
            raise ValueError(
                f"Tipo de archivo no soportado: {content_type}. "
                "Solo se aceptan imágenes y PDFs."
            )

        content = response.content
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(
                f"El archivo es demasiado grande ({len(content) / 1024 / 1024:.1f} MB). "
                f"Máximo permitido: {MAX_FILE_SIZE / 1024 / 1024:.0f} MB."
            )

        logger.info("Archivo descargado: %s (%s, %.1f KB)", url[:80], content_type, len(content) / 1024)
        return content, content_type
