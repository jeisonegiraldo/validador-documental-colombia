from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from google.cloud import firestore

from app.config import get_settings
from app.models import DocumentType, FlowState

logger = logging.getLogger(__name__)

COLLECTION = "document_validation_sessions"
EXTRACTED_COLLECTION = "extracted_documents"

_db: Optional[firestore.Client] = None


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        settings = get_settings()
        _db = firestore.Client(project=settings.GCP_PROJECT_ID)
    return _db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session() -> dict[str, Any]:
    """Create a new validation session in Firestore."""
    settings = get_settings()
    db = _get_db()

    session_id = str(uuid.uuid4())
    now = _now()
    session_data = {
        "session_id": session_id,
        "flow_state": FlowState.AWAITING_FIRST_UPLOAD.value,
        "document_type": DocumentType.UNKNOWN.value,
        "sides_received": {"front": None, "back": None},
        "single_page_path": None,
        "final_pdf_path": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(hours=settings.SESSION_TTL_HOURS),
    }

    db.collection(COLLECTION).document(session_id).set(session_data)
    logger.info("Session created: %s", session_id)
    return session_data


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a session by ID. Returns None if not found or expired."""
    db = _get_db()
    doc = db.collection(COLLECTION).document(session_id).get()
    if not doc.exists:
        return None

    data = doc.to_dict()

    expires_at = data.get("expires_at")
    if expires_at and expires_at.replace(tzinfo=timezone.utc) < _now():
        logger.info("Session expired: %s", session_id)
        delete_session(session_id)
        return None

    return data


def update_session(session_id: str, updates: dict[str, Any]) -> None:
    """Update specific fields on a session document."""
    db = _get_db()
    updates["updated_at"] = _now()
    db.collection(COLLECTION).document(session_id).update(updates)
    logger.info("Session updated: %s, fields: %s", session_id, list(updates.keys()))


def delete_session(session_id: str) -> None:
    """Delete a session document."""
    db = _get_db()
    db.collection(COLLECTION).document(session_id).delete()
    logger.info("Session deleted: %s", session_id)


def save_extracted_data(
    session_id: str,
    label: Optional[str],
    doc_type: str,
    extracted_data: dict[str, Any],
) -> None:
    """Persist extracted document data indefinitely (no TTL)."""
    db = _get_db()
    doc_data = {
        "session_id": session_id,
        "label": label,
        "document_type": doc_type,
        "extracted_data": extracted_data,
        "created_at": _now(),
    }
    db.collection(EXTRACTED_COLLECTION).document(session_id).set(doc_data)
    logger.info("Extracted data saved for session: %s (label=%s)", session_id, label)
