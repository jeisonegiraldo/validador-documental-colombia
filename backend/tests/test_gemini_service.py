"""Tests for the Gemini classification service."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from app.models import DocumentSide, DocumentType, GeminiClassificationResult
from app.services.gemini_service import classify_document


class TestClassifyDocument:

    @pytest.mark.asyncio
    @patch("app.services.gemini_service._get_client")
    @patch("app.services.gemini_service.get_settings")
    async def test_successful_classification(self, mock_settings, mock_client):
        settings = MagicMock()
        settings.GEMINI_MODEL = "gemini-2.0-flash"
        mock_settings.return_value = settings

        response_data = {
            "documentType": "cedula_ciudadania",
            "documentSide": "front",
            "isValidDocument": True,
            "isLegible": True,
            "containsBothSides": False,
            "userFeedback": "Cédula frontal válida.",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(response_data)

        client = MagicMock()
        client.models.generate_content.return_value = mock_response
        mock_client.return_value = client

        result = await classify_document(b"fake_image", "image/jpeg")

        assert isinstance(result, GeminiClassificationResult)
        assert result.documentType == DocumentType.CEDULA_CIUDADANIA
        assert result.documentSide == DocumentSide.FRONT
        assert result.isValidDocument is True
        assert result.isLegible is True

    @pytest.mark.asyncio
    @patch("app.services.gemini_service._get_client")
    @patch("app.services.gemini_service.get_settings")
    async def test_gemini_failure_returns_fallback(self, mock_settings, mock_client):
        settings = MagicMock()
        settings.GEMINI_MODEL = "gemini-2.0-flash"
        mock_settings.return_value = settings

        client = MagicMock()
        client.models.generate_content.side_effect = Exception("API error")
        mock_client.return_value = client

        result = await classify_document(b"fake_image", "image/jpeg")

        assert result.documentType == DocumentType.UNKNOWN
        assert result.isValidDocument is False
        assert "intenta de nuevo" in result.userFeedback.lower()

    @pytest.mark.asyncio
    @patch("app.services.gemini_service._get_client")
    @patch("app.services.gemini_service.get_settings")
    async def test_context_passed_to_prompt(self, mock_settings, mock_client):
        settings = MagicMock()
        settings.GEMINI_MODEL = "gemini-2.0-flash"
        mock_settings.return_value = settings

        response_data = {
            "documentType": "cedula_ciudadania",
            "documentSide": "back",
            "isValidDocument": True,
            "isLegible": True,
            "containsBothSides": False,
            "userFeedback": "Cara trasera recibida.",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(response_data)

        client = MagicMock()
        client.models.generate_content.return_value = mock_response
        mock_client.return_value = client

        result = await classify_document(
            b"fake_image",
            "image/jpeg",
            context="Se espera la cara TRASERA",
        )

        # Verify context was included in the prompt
        call_args = client.models.generate_content.call_args
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents") or call_args[0][1] if len(call_args[0]) > 1 else None
        assert result.documentSide == DocumentSide.BACK
