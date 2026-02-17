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


# --- Extracted data ---

class ExtractedField(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class ExtractedData(BaseModel):
    # Common (Cédula, Tarjeta ID)
    numeroDocumento: ExtractedField = Field(default_factory=ExtractedField)
    nombres: ExtractedField = Field(default_factory=ExtractedField)
    apellidos: ExtractedField = Field(default_factory=ExtractedField)
    fechaNacimiento: ExtractedField = Field(default_factory=ExtractedField)
    lugarNacimiento: ExtractedField = Field(default_factory=ExtractedField)
    sexo: ExtractedField = Field(default_factory=ExtractedField)
    fechaExpedicion: ExtractedField = Field(default_factory=ExtractedField)
    lugarExpedicion: ExtractedField = Field(default_factory=ExtractedField)
    # RC Nacimiento — padres
    nombresPadre: ExtractedField = Field(default_factory=ExtractedField)
    apellidosPadre: ExtractedField = Field(default_factory=ExtractedField)
    nombresMadre: ExtractedField = Field(default_factory=ExtractedField)
    apellidosMadre: ExtractedField = Field(default_factory=ExtractedField)
    # RC Matrimonio — contrayentes
    contrayente1Nombres: ExtractedField = Field(default_factory=ExtractedField)
    contrayente1Apellidos: ExtractedField = Field(default_factory=ExtractedField)
    contrayente1Documento: ExtractedField = Field(default_factory=ExtractedField)
    contrayente2Nombres: ExtractedField = Field(default_factory=ExtractedField)
    contrayente2Apellidos: ExtractedField = Field(default_factory=ExtractedField)
    contrayente2Documento: ExtractedField = Field(default_factory=ExtractedField)
    # RC Defunción
    fechaDefuncion: ExtractedField = Field(default_factory=ExtractedField)
    lugarDefuncion: ExtractedField = Field(default_factory=ExtractedField)


# Critical fields per document type (trigger alerts if confidence < 0.85)
CRITICAL_FIELDS: dict[DocumentType, list[str]] = {
    DocumentType.CEDULA_CIUDADANIA: [
        "numeroDocumento", "nombres", "apellidos", "fechaNacimiento",
    ],
    DocumentType.TARJETA_IDENTIDAD: [
        "numeroDocumento", "nombres", "apellidos", "fechaNacimiento",
    ],
    DocumentType.REGISTRO_CIVIL_NACIMIENTO: [
        "numeroDocumento", "nombres", "apellidos", "fechaNacimiento",
        "nombresPadre", "apellidosPadre", "nombresMadre", "apellidosMadre",
    ],
    DocumentType.REGISTRO_CIVIL_MATRIMONIO: [
        "numeroDocumento", "nombres", "apellidos",
        "contrayente1Nombres", "contrayente1Apellidos",
        "contrayente2Nombres", "contrayente2Apellidos",
    ],
    DocumentType.REGISTRO_CIVIL_DEFUNCION: [
        "numeroDocumento", "nombres", "apellidos", "fechaDefuncion",
    ],
}

FIELD_LABELS: dict[str, str] = {
    "numeroDocumento": "Número de documento",
    "nombres": "Nombres",
    "apellidos": "Apellidos",
    "fechaNacimiento": "Fecha de nacimiento",
    "lugarNacimiento": "Lugar de nacimiento",
    "sexo": "Sexo",
    "fechaExpedicion": "Fecha de expedición",
    "lugarExpedicion": "Lugar de expedición",
    "nombresPadre": "Nombres del padre",
    "apellidosPadre": "Apellidos del padre",
    "nombresMadre": "Nombres de la madre",
    "apellidosMadre": "Apellidos de la madre",
    "contrayente1Nombres": "Nombres contrayente 1",
    "contrayente1Apellidos": "Apellidos contrayente 1",
    "contrayente1Documento": "Documento contrayente 1",
    "contrayente2Nombres": "Nombres contrayente 2",
    "contrayente2Apellidos": "Apellidos contrayente 2",
    "contrayente2Documento": "Documento contrayente 2",
    "fechaDefuncion": "Fecha de defunción",
    "lugarDefuncion": "Lugar de defunción",
}


# --- Request / Response ---

class ValidateRequest(BaseModel):
    fileUrl: str = Field(..., description="URL pública del archivo (imagen o PDF)")
    sessionId: Optional[str] = Field(None, description="ID de sesión existente (para segunda cara)")
    label: Optional[str] = Field(None, description="Etiqueta opcional asignada por el orquestador (ej: cedula_reclamante)")


class ValidateResponse(BaseModel):
    sessionId: str
    status: FlowStatus
    documentType: DocumentType = DocumentType.UNKNOWN
    detectedSide: DocumentSide = DocumentSide.UNKNOWN
    isValid: bool = False
    isLegible: bool = False
    feedback: str = ""
    generatedPdfUrl: Optional[str] = None
    extractedData: Optional[ExtractedData] = None
    alerts: list[str] = Field(default_factory=list)
    label: Optional[str] = None


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
    extractedData: ExtractedData = Field(default_factory=ExtractedData)
