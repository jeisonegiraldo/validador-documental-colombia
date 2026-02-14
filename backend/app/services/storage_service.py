from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from google.cloud import storage

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[storage.Client] = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=get_settings().GCP_PROJECT_ID)
    return _client


def _get_bucket() -> storage.Bucket:
    settings = get_settings()
    return _get_client().bucket(settings.GCS_BUCKET_NAME)


def upload_bytes(data: bytes, destination_path: str, content_type: str = "image/jpeg") -> str:
    """Upload bytes to GCS and return the gs:// URI."""
    bucket = _get_bucket()
    blob = bucket.blob(destination_path)
    blob.upload_from_string(data, content_type=content_type)
    gs_uri = f"gs://{bucket.name}/{destination_path}"
    logger.info("Uploaded to %s (%d bytes)", gs_uri, len(data))
    return gs_uri


def download_bytes(gs_path: str) -> bytes:
    """Download bytes from a gs:// URI."""
    bucket = _get_bucket()
    # Strip gs://bucket-name/ prefix
    blob_name = gs_path.replace(f"gs://{bucket.name}/", "")
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()


def generate_signed_url(gs_path: str) -> str:
    """Generate a signed URL for a GCS object."""
    settings = get_settings()
    bucket = _get_bucket()
    blob_name = gs_path.replace(f"gs://{bucket.name}/", "")
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=settings.SIGNED_URL_EXPIRATION_MINUTES),
        method="GET",
    )
    return url


def delete_session_files(session_id: str) -> None:
    """Delete all files under sessions/{session_id}/."""
    bucket = _get_bucket()
    prefix = f"sessions/{session_id}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    for blob in blobs:
        blob.delete()
    logger.info("Deleted %d files for session %s", len(blobs), session_id)


def session_path(session_id: str, filename: str) -> str:
    """Build a GCS object path for a session file."""
    return f"sessions/{session_id}/{filename}"
