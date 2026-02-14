from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_gemini_api_key, get_settings
from app.models import (
    DocumentSide,
    DocumentType,
    GeminiClassificationResult,
)

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = get_gemini_api_key()
        _client = genai.Client(api_key=api_key)
    return _client


CLASSIFICATION_PROMPT = """\
Eres un experto en documentos de identidad colombianos. Analiza la imagen proporcionada y clasifícala.

TIPOS DE DOCUMENTO que debes identificar:
- cedula_ciudadania: Cédula de Ciudadanía colombiana (documento plastificado con foto, nombre, número)
- tarjeta_identidad: Tarjeta de Identidad colombiana (para menores de edad, similar a cédula)
- registro_civil_nacimiento: Registro Civil de Nacimiento (documento en papel, formato formulario)
- registro_civil_matrimonio: Registro Civil de Matrimonio (documento en papel)
- registro_civil_defuncion: Registro Civil de Defunción (documento en papel)
- unknown: No es ninguno de los documentos anteriores

CARAS del documento:
- front: Cara frontal (tiene la foto y datos principales)
- back: Cara trasera (tiene código de barras, huella, datos adicionales)
- full_document: La imagen/PDF contiene AMBAS caras del documento
- single_page: Documento de una sola página (registros civiles)
- unknown: No se puede determinar

INSTRUCCIONES:
1. Determina el tipo de documento
2. Determina qué cara se muestra
3. Evalúa si es un documento válido (no una fotocopia de mala calidad, no un documento de otro país, no algo completamente diferente)
4. Evalúa si el documento es LEGIBLE (texto claro, no borroso, no cortado, bien iluminado)
5. Indica si la imagen contiene ambas caras del documento
6. Proporciona retroalimentación útil en español sencillo para el usuario

{context}

Responde ÚNICAMENTE con JSON válido con esta estructura exacta:
{{
  "documentType": "cedula_ciudadania|tarjeta_identidad|registro_civil_nacimiento|registro_civil_matrimonio|registro_civil_defuncion|unknown",
  "documentSide": "front|back|full_document|single_page|unknown",
  "isValidDocument": true/false,
  "isLegible": true/false,
  "containsBothSides": true/false,
  "userFeedback": "Mensaje descriptivo en español"
}}
"""


async def classify_document(
    file_bytes: bytes,
    mime_type: str,
    context: str = "",
) -> GeminiClassificationResult:
    """Classify a document image using Gemini.

    Args:
        file_bytes: Raw file bytes (image or PDF).
        mime_type: MIME type of the file.
        context: Optional context hint (e.g. "Se espera la cara TRASERA").

    Returns:
        GeminiClassificationResult with classification details.
    """
    settings = get_settings()
    client = _get_client()

    context_section = f"CONTEXTO ADICIONAL: {context}" if context else ""
    prompt = CLASSIFICATION_PROMPT.format(context=context_section)

    file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

    last_error = None
    for attempt in range(2):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=[file_part, prompt],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=2048),
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "documentType": {
                                "type": "string",
                                "enum": [e.value for e in DocumentType],
                            },
                            "documentSide": {
                                "type": "string",
                                "enum": [e.value for e in DocumentSide],
                            },
                            "isValidDocument": {"type": "boolean"},
                            "isLegible": {"type": "boolean"},
                            "containsBothSides": {"type": "boolean"},
                            "userFeedback": {"type": "string"},
                        },
                        "required": [
                            "documentType",
                            "documentSide",
                            "isValidDocument",
                            "isLegible",
                            "containsBothSides",
                            "userFeedback",
                        ],
                    },
                ),
            )

            result_text = response.text
            result_data = json.loads(result_text)
            return GeminiClassificationResult(**result_data)

        except Exception as e:
            last_error = e
            logger.warning("Gemini attempt %d failed: %s", attempt + 1, e)
            if attempt == 0:
                await asyncio.sleep(2)

    logger.error("Gemini classification failed after retries: %s", last_error)
    return GeminiClassificationResult(
        documentType=DocumentType.UNKNOWN,
        documentSide=DocumentSide.UNKNOWN,
        isValidDocument=False,
        isLegible=False,
        containsBothSides=False,
        userFeedback="No pudimos analizar el documento en este momento. Por favor, intenta de nuevo.",
    )
