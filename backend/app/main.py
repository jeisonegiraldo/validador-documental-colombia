from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    DocumentType,
    FlowState,
    FlowStatus,
    SessionResponse,
    ValidateRequest,
    ValidateResponse,
)
from app.services import file_fetcher, firestore_service, storage_service
from app.state_machine import process_upload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Validador Documental Colombia",
    description="API para validación de documentos de identidad colombianos",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health check ---

@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Validate endpoint ---

@app.post("/api/v1/validate", response_model=ValidateResponse)
async def validate_document(request: ValidateRequest):
    """Validate a Colombian identity document from a file URL."""
    try:
        # 1. Download file
        try:
            file_bytes, mime_type = await file_fetcher.fetch_file(request.fileUrl)
        except ValueError as e:
            return ValidateResponse(
                sessionId=request.sessionId or "",
                status=FlowStatus.ERROR,
                feedback=str(e),
            )
        except Exception as e:
            logger.error("File download failed: %s", e)
            return ValidateResponse(
                sessionId=request.sessionId or "",
                status=FlowStatus.ERROR,
                feedback="No se pudo descargar el archivo. Verifica que la URL sea válida y accesible.",
            )

        # 2. Process through state machine
        result = await process_upload(
            file_bytes=file_bytes,
            mime_type=mime_type,
            session_id=request.sessionId,
        )

        return result

    except Exception as e:
        logger.exception("Unexpected error in validate_document")
        return ValidateResponse(
            sessionId=request.sessionId or "",
            status=FlowStatus.ERROR,
            feedback="Ocurrió un error inesperado. Por favor, intenta de nuevo más tarde.",
        )


# --- Session endpoints ---

@app.get("/api/v1/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a validation session."""
    session = firestore_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada.")

    return SessionResponse(
        sessionId=session["session_id"],
        flowState=FlowState(session["flow_state"]),
        documentType=DocumentType(session["document_type"]),
        sidesReceived=session.get("sides_received", {}),
        createdAt=str(session.get("created_at", "")),
        updatedAt=str(session.get("updated_at", "")),
    )


@app.delete("/api/v1/session/{session_id}")
async def delete_session(session_id: str):
    """Cancel a session and clean up associated files."""
    session = firestore_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada.")

    # Clean up GCS files
    try:
        storage_service.delete_session_files(session_id)
    except Exception as e:
        logger.warning("Failed to clean GCS files for session %s: %s", session_id, e)

    # Delete Firestore document
    firestore_service.delete_session(session_id)

    return {"message": "Sesión eliminada exitosamente.", "sessionId": session_id}
