from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

import google.auth
from google.auth import compute_engine
from google.auth.transport import requests as auth_requests
from google.cloud import storage

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[storage.Client] = None
_signing_credentials: Optional[compute_engine.IDTokenCredentials] = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=get_settings().GCP_PROJECT_ID)
    return _client


def _get_signing_credentials():
    """Get credentials capable of signing, using IAM signBlob on Cloud Run."""
    global _signing_credentials
    if _signing_credentials is None:
        credentials, _ = google.auth.default()
        if isinstance(credentials, compute_engine.Credentials):
            _signing_credentials = credentials
        else:
            # Local dev — credentials can sign directly
            _signing_credentials = None
    return _signing_credentials


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
    """Generate a signed URL for a GCS object.

    On Cloud Run (Compute Engine credentials), uses IAM signBlob via the
    service_account_email so no private key is needed locally.
    """
    settings = get_settings()
    bucket = _get_bucket()
    blob_name = gs_path.replace(f"gs://{bucket.name}/", "")
    blob = bucket.blob(blob_name)

    signing_creds = _get_signing_credentials()
    if signing_creds is not None and isinstance(signing_creds, compute_engine.Credentials):
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=settings.SIGNED_URL_EXPIRATION_MINUTES),
            method="GET",
            service_account_email=signing_creds.service_account_email,
            access_token=signing_creds.token,
        )
        # If token was not yet fetched, refresh and retry
        if not signing_creds.token:
            signing_creds.refresh(auth_requests.Request())
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=settings.SIGNED_URL_EXPIRATION_MINUTES),
                method="GET",
                service_account_email=signing_creds.service_account_email,
                access_token=signing_creds.token,
            )
    else:
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
