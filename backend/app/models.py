from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    CEDULA_CIUDADANIA = "cedula_ciudadania"
    TARJETA_IDENTIDAD = "tarjeta_identidad"
    REGISTRO_CIVIL_NACIMIENTO = "registro_civil_nacimiento"
    REGISTRO_CIVIL_MATRIMONIO = "registro_civil_matrimonio"
    REGISTRO_CIVIL_DEFUNCION = "registro_civil_defuncion"
    UNKNOWN = "unknown"


class DocumentSide(str, Enum):
    FRONT = "front"
    BACK = "back"
    FULL_DOCUMENT = "full_document"
    SINGLE_PAGE = "single_page"
    UNKNOWN = "unknown"


class FlowStatus(str, Enum):
    NEEDS_BACK_SIDE = "needs_back_side"
    NEEDS_FRONT_SIDE = "needs_front_side"
    NEEDS_BETTER_IMAGE = "needs_better_image"
    COMPLETED = "completed"
    INVALID_DOCUMENT = "invalid_document"
    ERROR = "error"


class FlowState(str, Enum):
    AWAITING_FIRST_UPLOAD = "AWAITING_FIRST_UPLOAD"
    AWAITING_SECOND_SIDE = "AWAITING_SECOND_SIDE"
    PROCESSING_PDF = "PROCESSING_PDF"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


# Documents that require two sides (front + back)
TWO_SIDED_DOCUMENTS = {DocumentType.CEDULA_CIUDADANIA, DocumentType.TARJETA_IDENTIDAD}

# Documents that are single-page
SINGLE_PAGE_DOCUMENTS = {
    DocumentType.REGISTRO_CIVIL_NACIMIENTO,
    DocumentType.REGISTRO_CIVIL_MATRIMONIO,
    DocumentType.REGISTRO_CIVIL_DEFUNCION,
}

DOCUMENT_TYPE_LABELS = {
    DocumentType.CEDULA_CIUDADANIA: "Cédula de Ciudadanía",
    DocumentType.TARJETA_IDENTIDAD: "Tarjeta de Identidad",
    DocumentType.REGISTRO_CIVIL_NACIMIENTO: "Registro Civil de Nacimiento",
    DocumentType.REGISTRO_CIVIL_MATRIMONIO: "Registro Civil de Matrimonio",
    DocumentType.REGISTRO_CIVIL_DEFUNCION: "Registro Civil de Defunción",
    DocumentType.UNKNOWN: "Documento desconocido",
}


# --- Request / Response ---

class ValidateRequest(BaseModel):
    fileUrl: str = Field(..., description="URL pública del archivo (imagen o PDF)")
    sessionId: Optional[str] = Field(None, description="ID de sesión existente (para segunda cara)")


class ValidateResponse(BaseModel):
    sessionId: str
    status: FlowStatus
    documentType: DocumentType = DocumentType.UNKNOWN
    detectedSide: DocumentSide = DocumentSide.UNKNOWN
    isValid: bool = False
    isLegible: bool = False
    feedback: str = ""
    generatedPdfUrl: Optional[str] = None


class SessionResponse(BaseModel):
    sessionId: str
    flowState: FlowState
    documentType: DocumentType
    sidesReceived: dict
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


# --- Gemini result ---

class GeminiClassificationResult(BaseModel):
    documentType: DocumentType = DocumentType.UNKNOWN
    documentSide: DocumentSide = DocumentSide.UNKNOWN
    isValidDocument: bool = False
    isLegible: bool = False
    containsBothSides: bool = False
    userFeedback: str = ""
