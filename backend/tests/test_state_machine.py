"""Tests for the state machine orchestration logic."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import (
    DocumentSide,
    DocumentType,
    FlowState,
    FlowStatus,
    GeminiClassificationResult,
)
from app.state_machine import process_upload


@pytest.fixture
def mock_session_new():
    return {
        "session_id": "test-session-1",
        "flow_state": FlowState.AWAITING_FIRST_UPLOAD.value,
        "document_type": DocumentType.UNKNOWN.value,
        "sides_received": {"front": None, "back": None},
        "single_page_path": None,
        "final_pdf_path": None,
    }


@pytest.fixture
def mock_session_awaiting_back():
    return {
        "session_id": "test-session-2",
        "flow_state": FlowState.AWAITING_SECOND_SIDE.value,
        "document_type": DocumentType.CEDULA_CIUDADANIA.value,
        "sides_received": {"front": "gs://bucket/sessions/test-session-2/enhanced_front.jpg", "back": None},
        "single_page_path": None,
        "final_pdf_path": None,
    }


@pytest.fixture
def classification_front_cedula():
    return GeminiClassificationResult(
        documentType=DocumentType.CEDULA_CIUDADANIA,
        documentSide=DocumentSide.FRONT,
        isValidDocument=True,
        isLegible=True,
        containsBothSides=False,
        userFeedback="Cara frontal de Cédula de Ciudadanía recibida correctamente.",
    )


@pytest.fixture
def classification_back_cedula():
    return GeminiClassificationResult(
        documentType=DocumentType.CEDULA_CIUDADANIA,
        documentSide=DocumentSide.BACK,
        isValidDocument=True,
        isLegible=True,
        containsBothSides=False,
        userFeedback="Cara trasera recibida. Documento completo.",
    )


@pytest.fixture
def classification_invalid():
    return GeminiClassificationResult(
        documentType=DocumentType.UNKNOWN,
        documentSide=DocumentSide.UNKNOWN,
        isValidDocument=False,
        isLegible=False,
        containsBothSides=False,
        userFeedback="No se reconoce como un documento de identidad colombiano.",
    )


@pytest.fixture
def classification_illegible():
    return GeminiClassificationResult(
        documentType=DocumentType.CEDULA_CIUDADANIA,
        documentSide=DocumentSide.FRONT,
        isValidDocument=True,
        isLegible=False,
        containsBothSides=False,
        userFeedback="La imagen está borrosa. Por favor, toma una foto más clara.",
    )


@pytest.fixture
def classification_registro_civil():
    return GeminiClassificationResult(
        documentType=DocumentType.REGISTRO_CIVIL_NACIMIENTO,
        documentSide=DocumentSide.SINGLE_PAGE,
        isValidDocument=True,
        isLegible=True,
        containsBothSides=False,
        userFeedback="Registro Civil de Nacimiento recibido correctamente.",
    )


class TestFirstUpload:
    """Tests for AWAITING_FIRST_UPLOAD state."""

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    @patch("app.state_machine.storage_service")
    async def test_new_session_front_cedula(
        self, mock_storage, mock_image, mock_gemini, mock_firestore,
        mock_session_new, classification_front_cedula,
    ):
        mock_firestore.create_session.return_value = mock_session_new
        mock_image.enhance_image.return_value = b"enhanced"
        mock_gemini.classify_document = AsyncMock(return_value=classification_front_cedula)
        mock_storage.session_path.return_value = "sessions/test-session-1/enhanced_front.jpg"
        mock_storage.upload_bytes.return_value = "gs://bucket/sessions/test-session-1/enhanced_front.jpg"

        result = await process_upload(b"image_bytes", "image/jpeg", None)

        assert result.sessionId == "test-session-1"
        assert result.status == FlowStatus.NEEDS_BACK_SIDE
        assert result.documentType == DocumentType.CEDULA_CIUDADANIA
        assert result.isValid is True
        mock_firestore.update_session.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    async def test_invalid_document(
        self, mock_image, mock_gemini, mock_firestore,
        mock_session_new, classification_invalid,
    ):
        mock_firestore.create_session.return_value = mock_session_new
        mock_image.enhance_image.return_value = b"enhanced"
        mock_gemini.classify_document = AsyncMock(return_value=classification_invalid)

        result = await process_upload(b"image_bytes", "image/jpeg", None)

        assert result.status == FlowStatus.INVALID_DOCUMENT
        assert result.isValid is False

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    async def test_illegible_document(
        self, mock_image, mock_gemini, mock_firestore,
        mock_session_new, classification_illegible,
    ):
        mock_firestore.create_session.return_value = mock_session_new
        mock_image.enhance_image.return_value = b"enhanced"
        mock_gemini.classify_document = AsyncMock(return_value=classification_illegible)

        result = await process_upload(b"image_bytes", "image/jpeg", None)

        assert result.status == FlowStatus.NEEDS_BETTER_IMAGE
        assert result.isLegible is False

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    @patch("app.state_machine.storage_service")
    @patch("app.state_machine.pdf_service")
    async def test_single_page_registro_civil(
        self, mock_pdf, mock_storage, mock_image, mock_gemini, mock_firestore,
        mock_session_new, classification_registro_civil,
    ):
        mock_firestore.create_session.return_value = mock_session_new
        mock_image.enhance_image.return_value = b"enhanced"
        mock_gemini.classify_document = AsyncMock(return_value=classification_registro_civil)
        mock_pdf.generate_single_page_pdf.return_value = b"%PDF-fake"
        mock_pdf.is_valid_pdf.return_value = False
        mock_storage.session_path.side_effect = lambda sid, f: f"sessions/{sid}/{f}"
        mock_storage.upload_bytes.return_value = "gs://bucket/path"
        mock_storage.generate_signed_url.return_value = "https://signed-url"

        result = await process_upload(b"image_bytes", "image/jpeg", None)

        assert result.status == FlowStatus.COMPLETED
        assert result.documentType == DocumentType.REGISTRO_CIVIL_NACIMIENTO
        assert result.generatedPdfUrl == "https://signed-url"


class TestSecondSide:
    """Tests for AWAITING_SECOND_SIDE state."""

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    @patch("app.state_machine.storage_service")
    @patch("app.state_machine.pdf_service")
    async def test_back_side_completes_session(
        self, mock_pdf, mock_storage, mock_image, mock_gemini, mock_firestore,
        mock_session_awaiting_back, classification_back_cedula,
    ):
        mock_firestore.get_session.return_value = mock_session_awaiting_back
        mock_image.enhance_image.return_value = b"enhanced_back"
        mock_gemini.classify_document = AsyncMock(return_value=classification_back_cedula)
        mock_pdf.generate_two_sided_pdf.return_value = b"%PDF-consolidated"
        mock_storage.session_path.side_effect = lambda sid, f: f"sessions/{sid}/{f}"
        mock_storage.upload_bytes.return_value = "gs://bucket/path"
        mock_storage.download_bytes.return_value = b"front_bytes"
        mock_storage.generate_signed_url.return_value = "https://signed-url"

        result = await process_upload(b"back_image", "image/jpeg", "test-session-2")

        assert result.status == FlowStatus.COMPLETED
        assert result.generatedPdfUrl == "https://signed-url"
        mock_pdf.generate_two_sided_pdf.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    async def test_same_side_repeated(
        self, mock_image, mock_gemini, mock_firestore,
        mock_session_awaiting_back, classification_front_cedula,
    ):
        mock_firestore.get_session.return_value = mock_session_awaiting_back
        mock_image.enhance_image.return_value = b"enhanced"
        mock_gemini.classify_document = AsyncMock(return_value=classification_front_cedula)

        result = await process_upload(b"front_again", "image/jpeg", "test-session-2")

        assert result.status == FlowStatus.NEEDS_BACK_SIDE
        assert "frontal" in result.feedback.lower() or "TRASERA" in result.feedback

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    @patch("app.state_machine.gemini_service")
    @patch("app.state_machine.image_service")
    async def test_different_document_type_rejected(
        self, mock_image, mock_gemini, mock_firestore,
        mock_session_awaiting_back,
    ):
        mock_firestore.get_session.return_value = mock_session_awaiting_back
        mock_image.enhance_image.return_value = b"enhanced"

        wrong_type = GeminiClassificationResult(
            documentType=DocumentType.TARJETA_IDENTIDAD,
            documentSide=DocumentSide.BACK,
            isValidDocument=True,
            isLegible=True,
            containsBothSides=False,
            userFeedback="Tarjeta de identidad detectada.",
        )
        mock_gemini.classify_document = AsyncMock(return_value=wrong_type)

        result = await process_upload(b"wrong_doc", "image/jpeg", "test-session-2")

        assert result.status == FlowStatus.NEEDS_BACK_SIDE
        assert "diferente" in result.feedback.lower()


class TestExpiredSession:
    """Tests for expired/missing sessions."""

    @pytest.mark.asyncio
    @patch("app.state_machine.firestore_service")
    async def test_expired_session_returns_error(self, mock_firestore):
        mock_firestore.get_session.return_value = None

        result = await process_upload(b"data", "image/jpeg", "expired-id")

        assert result.status == FlowStatus.ERROR
        assert "expirado" in result.feedback.lower() or "no existe" in result.feedback.lower()
