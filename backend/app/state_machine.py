from __future__ import annotations

import logging
from typing import Any

from app.models import (
    DocumentSide,
    DocumentType,
    FlowState,
    FlowStatus,
    GeminiClassificationResult,
    ValidateResponse,
    SINGLE_PAGE_DOCUMENTS,
    TWO_SIDED_DOCUMENTS,
)
from app.services import (
    firestore_service,
    gemini_service,
    image_service,
    pdf_service,
    storage_service,
)

logger = logging.getLogger(__name__)


async def process_upload(
    file_bytes: bytes,
    mime_type: str,
    session_id: str | None,
) -> ValidateResponse:
    """Main orchestration: classify the document and advance the session state."""

    # 1. Get or create session
    if session_id:
        session = firestore_service.get_session(session_id)
        if session is None:
            return ValidateResponse(
                sessionId=session_id,
                status=FlowStatus.ERROR,
                feedback="La sesión no existe o ha expirado. Envía el documento nuevamente para iniciar una nueva sesión.",
            )
    else:
        session = firestore_service.create_session()
        session_id = session["session_id"]

    flow_state = FlowState(session["flow_state"])

    # If session is already completed, return error
    if flow_state == FlowState.COMPLETED:
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.COMPLETED,
            documentType=DocumentType(session["document_type"]),
            feedback="Esta sesión ya fue completada. Envía el documento nuevamente para iniciar una nueva validación.",
        )

    # 2. Enhance image (skip for PDFs)
    is_pdf = mime_type == "application/pdf"
    if not is_pdf:
        enhanced_bytes = image_service.enhance_image(file_bytes)
    else:
        enhanced_bytes = file_bytes

    # 3. Build context for Gemini
    context = _build_context(session)

    # 4. Classify with Gemini
    classification = await gemini_service.classify_document(
        file_bytes=enhanced_bytes,
        mime_type=mime_type,
        context=context,
    )

    # 5. Process based on current state
    if flow_state == FlowState.AWAITING_FIRST_UPLOAD:
        return await _handle_first_upload(session_id, session, classification, enhanced_bytes, is_pdf)
    elif flow_state == FlowState.AWAITING_SECOND_SIDE:
        return await _handle_second_side(session_id, session, classification, enhanced_bytes, is_pdf)
    else:
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.ERROR,
            feedback="Estado de sesión inesperado. Por favor, inicia una nueva sesión.",
        )


def _build_context(session: dict[str, Any]) -> str:
    """Build context string for Gemini based on session state."""
    flow_state = FlowState(session["flow_state"])
    if flow_state != FlowState.AWAITING_SECOND_SIDE:
        return ""

    sides = session.get("sides_received", {})
    doc_type = session.get("document_type", "unknown")

    if sides.get("front") and not sides.get("back"):
        return f"Se espera la cara TRASERA de un documento tipo '{doc_type}'. Ya se recibió la cara frontal."
    elif sides.get("back") and not sides.get("front"):
        return f"Se espera la cara FRONTAL de un documento tipo '{doc_type}'. Ya se recibió la cara trasera."
    return ""


async def _handle_first_upload(
    session_id: str,
    session: dict[str, Any],
    classification: GeminiClassificationResult,
    enhanced_bytes: bytes,
    is_pdf: bool,
) -> ValidateResponse:
    """Handle the first document upload."""
    doc_type = classification.documentType
    side = classification.documentSide

    # Invalid document
    if not classification.isValidDocument or doc_type == DocumentType.UNKNOWN:
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.INVALID_DOCUMENT,
            documentType=doc_type,
            detectedSide=side,
            isValid=False,
            isLegible=classification.isLegible,
            feedback=classification.userFeedback,
        )

    # Not legible
    if not classification.isLegible:
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.NEEDS_BETTER_IMAGE,
            documentType=doc_type,
            detectedSide=side,
            isValid=True,
            isLegible=False,
            feedback=classification.userFeedback,
        )

    # Single-page document → complete immediately
    if doc_type in SINGLE_PAGE_DOCUMENTS:
        return await _complete_single_page(session_id, doc_type, side, classification, enhanced_bytes, is_pdf)

    # Two-sided document with both sides in one image/PDF
    if classification.containsBothSides and side == DocumentSide.FULL_DOCUMENT:
        return await _complete_full_document(session_id, doc_type, classification, enhanced_bytes, is_pdf)

    # Two-sided document: got one side, need the other
    if doc_type in TWO_SIDED_DOCUMENTS:
        return await _save_first_side(session_id, doc_type, side, classification, enhanced_bytes)

    # Fallback for unexpected cases
    return ValidateResponse(
        sessionId=session_id,
        status=FlowStatus.ERROR,
        documentType=doc_type,
        detectedSide=side,
        feedback="No se pudo procesar el documento. Por favor, intenta de nuevo.",
    )


async def _handle_second_side(
    session_id: str,
    session: dict[str, Any],
    classification: GeminiClassificationResult,
    enhanced_bytes: bytes,
    is_pdf: bool,
) -> ValidateResponse:
    """Handle the second side upload for two-sided documents."""
    expected_type = DocumentType(session["document_type"])
    doc_type = classification.documentType
    side = classification.documentSide
    sides = session.get("sides_received", {})

    # Invalid or illegible
    if not classification.isValidDocument:
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.INVALID_DOCUMENT,
            documentType=doc_type,
            detectedSide=side,
            isValid=False,
            isLegible=classification.isLegible,
            feedback=classification.userFeedback,
        )

    if not classification.isLegible:
        # Determine which side is still needed
        status = FlowStatus.NEEDS_BACK_SIDE if sides.get("front") else FlowStatus.NEEDS_FRONT_SIDE
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.NEEDS_BETTER_IMAGE,
            documentType=expected_type,
            detectedSide=side,
            isValid=True,
            isLegible=False,
            feedback=classification.userFeedback,
        )

    # Document type consistency check
    if doc_type != expected_type and doc_type != DocumentType.UNKNOWN:
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.NEEDS_BACK_SIDE if sides.get("front") else FlowStatus.NEEDS_FRONT_SIDE,
            documentType=expected_type,
            detectedSide=side,
            isValid=True,
            isLegible=True,
            feedback=(
                f"El documento enviado parece ser un tipo diferente al esperado. "
                f"Se espera continuar con la misma {_label(expected_type)}. "
                f"Por favor, envía la cara faltante del mismo documento."
            ),
        )

    # Check if same side was sent again
    if side == DocumentSide.FRONT and sides.get("front"):
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.NEEDS_BACK_SIDE,
            documentType=expected_type,
            detectedSide=side,
            isValid=True,
            isLegible=True,
            feedback="Ya recibimos la cara frontal. Por favor, envía la cara TRASERA del documento.",
        )

    if side == DocumentSide.BACK and sides.get("back"):
        return ValidateResponse(
            sessionId=session_id,
            status=FlowStatus.NEEDS_FRONT_SIDE,
            documentType=expected_type,
            detectedSide=side,
            isValid=True,
            isLegible=True,
            feedback="Ya recibimos la cara trasera. Por favor, envía la cara FRONTAL del documento.",
        )

    # Full document in second upload
    if classification.containsBothSides and side == DocumentSide.FULL_DOCUMENT:
        return await _complete_full_document(session_id, expected_type, classification, enhanced_bytes, is_pdf)

    # Save second side and generate PDF
    return await _complete_two_sides(session_id, session, expected_type, side, classification, enhanced_bytes)


async def _save_first_side(
    session_id: str,
    doc_type: DocumentType,
    side: DocumentSide,
    classification: GeminiClassificationResult,
    enhanced_bytes: bytes,
) -> ValidateResponse:
    """Save the first side and ask for the other."""
    filename = "enhanced_front.jpg" if side == DocumentSide.FRONT else "enhanced_back.jpg"
    gcs_path = storage_service.session_path(session_id, filename)
    storage_service.upload_bytes(enhanced_bytes, gcs_path)

    side_key = "front" if side == DocumentSide.FRONT else "back"
    firestore_service.update_session(session_id, {
        "flow_state": FlowState.AWAITING_SECOND_SIDE.value,
        "document_type": doc_type.value,
        f"sides_received.{side_key}": gcs_path,
    })

    if side == DocumentSide.FRONT:
        status = FlowStatus.NEEDS_BACK_SIDE
    else:
        status = FlowStatus.NEEDS_FRONT_SIDE

    return ValidateResponse(
        sessionId=session_id,
        status=status,
        documentType=doc_type,
        detectedSide=side,
        isValid=True,
        isLegible=True,
        feedback=classification.userFeedback,
    )


async def _complete_two_sides(
    session_id: str,
    session: dict[str, Any],
    doc_type: DocumentType,
    new_side: DocumentSide,
    classification: GeminiClassificationResult,
    enhanced_bytes: bytes,
) -> ValidateResponse:
    """Save the second side, generate consolidated PDF, and complete the session."""
    # Save new side
    filename = "enhanced_front.jpg" if new_side == DocumentSide.FRONT else "enhanced_back.jpg"
    gcs_path = storage_service.session_path(session_id, filename)
    storage_service.upload_bytes(enhanced_bytes, gcs_path)

    side_key = "front" if new_side == DocumentSide.FRONT else "back"
    sides = session.get("sides_received", {})

    # Determine which sides we have
    if new_side == DocumentSide.FRONT:
        front_bytes = enhanced_bytes
        back_bytes = storage_service.download_bytes(sides["back"])
    else:
        front_bytes = storage_service.download_bytes(sides["front"])
        back_bytes = enhanced_bytes

    # Generate PDF
    pdf_bytes = pdf_service.generate_two_sided_pdf(front_bytes, back_bytes, doc_type)
    pdf_path = storage_service.session_path(session_id, "final.pdf")
    storage_service.upload_bytes(pdf_bytes, pdf_path, content_type="application/pdf")

    signed_url = storage_service.generate_signed_url(pdf_path)

    # Update session
    firestore_service.update_session(session_id, {
        "flow_state": FlowState.COMPLETED.value,
        f"sides_received.{side_key}": gcs_path,
        "final_pdf_path": pdf_path,
    })

    return ValidateResponse(
        sessionId=session_id,
        status=FlowStatus.COMPLETED,
        documentType=doc_type,
        detectedSide=new_side,
        isValid=True,
        isLegible=True,
        feedback=classification.userFeedback,
        generatedPdfUrl=signed_url,
    )


async def _complete_single_page(
    session_id: str,
    doc_type: DocumentType,
    side: DocumentSide,
    classification: GeminiClassificationResult,
    enhanced_bytes: bytes,
    is_pdf: bool,
) -> ValidateResponse:
    """Handle single-page document completion."""
    # If it's already a valid PDF, use it directly
    if is_pdf and pdf_service.is_valid_pdf(enhanced_bytes):
        pdf_bytes = enhanced_bytes
    else:
        pdf_bytes = pdf_service.generate_single_page_pdf(enhanced_bytes, doc_type)

    # Upload source image and PDF
    img_path = storage_service.session_path(session_id, "source.jpg")
    storage_service.upload_bytes(enhanced_bytes, img_path)

    pdf_path = storage_service.session_path(session_id, "final.pdf")
    storage_service.upload_bytes(pdf_bytes, pdf_path, content_type="application/pdf")

    signed_url = storage_service.generate_signed_url(pdf_path)

    firestore_service.update_session(session_id, {
        "flow_state": FlowState.COMPLETED.value,
        "document_type": doc_type.value,
        "single_page_path": img_path,
        "final_pdf_path": pdf_path,
    })

    return ValidateResponse(
        sessionId=session_id,
        status=FlowStatus.COMPLETED,
        documentType=doc_type,
        detectedSide=side,
        isValid=True,
        isLegible=True,
        feedback=classification.userFeedback,
        generatedPdfUrl=signed_url,
    )


async def _complete_full_document(
    session_id: str,
    doc_type: DocumentType,
    classification: GeminiClassificationResult,
    file_bytes: bytes,
    is_pdf: bool,
) -> ValidateResponse:
    """Handle full document (both sides in one image/PDF)."""
    if is_pdf and pdf_service.is_valid_pdf(file_bytes):
        pdf_bytes = file_bytes
    else:
        pdf_bytes = pdf_service.generate_single_page_pdf(file_bytes, doc_type)

    pdf_path = storage_service.session_path(session_id, "final.pdf")
    storage_service.upload_bytes(pdf_bytes, pdf_path, content_type="application/pdf")

    source_path = storage_service.session_path(session_id, "source.pdf" if is_pdf else "source.jpg")
    storage_service.upload_bytes(file_bytes, source_path)

    signed_url = storage_service.generate_signed_url(pdf_path)

    firestore_service.update_session(session_id, {
        "flow_state": FlowState.COMPLETED.value,
        "document_type": doc_type.value,
        "single_page_path": source_path,
        "final_pdf_path": pdf_path,
    })

    return ValidateResponse(
        sessionId=session_id,
        status=FlowStatus.COMPLETED,
        documentType=doc_type,
        detectedSide=DocumentSide.FULL_DOCUMENT,
        isValid=True,
        isLegible=True,
        feedback=classification.userFeedback,
        generatedPdfUrl=signed_url,
    )


def _label(doc_type: DocumentType) -> str:
    from app.models import DOCUMENT_TYPE_LABELS
    return DOCUMENT_TYPE_LABELS.get(doc_type, "documento")
