"""Modelos de petición y respuesta de documentos (SPEC-W-002 §5.1 y §5.3). De ellos sale el cliente TypeScript.

`Review` es lo único que escribe la persona: se valida con `extra="forbid"`, importes enteros ESTRICTOS en céntimos (ni `12.5`, ni
`"120.00"`: lo que no se puede interpretar lo señala la interfaz junto al campo y no llega aquí), fechas ISO y longitudes. Valida la
forma, no la fiscalidad (SPEC-W-003).
"""

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationInfo, field_validator

from cuadre.agents.text import clean_text
from cuadre.expenses.validation_models import Validation

DocumentStatus = Literal["uploading", "processing", "review", "extraction_failed", "discarded", "registered"]
DocType = Literal["full_invoice", "simplified_invoice", "ticket", "receipt", "other", "not_an_invoice"]
DoubtField = Literal[
    "doc_type",
    "supplier_name",
    "supplier_tax_id",
    "recipient_tax_id",
    "invoice_number",
    "issue_date",
    "currency",
    "tax_breakdown",
    "withholding",
    "total",
]
DoubtReason = Literal["illegible", "ambiguous", "missing", "inconsistent"]
FailureCodeName = Literal[
    "unreadable",
    "unsupported_media_type",
    "payload_too_large",
    "timeout",
    "upstream_error",
    "agents_unavailable",
    "invalid_response",
    "internal",
]

# 12 cifras enteras + 2 decimales, como el contrato y la CHECK de la base de datos (15 cifras como mucho).
CENTS_MAX = 10**14 - 1
Cents = Annotated[StrictInt, Field(ge=-CENTS_MAX, le=CENTS_MAX)]
RATE = r"^[0-9]{1,3}(\.[0-9]{1,2})?$"
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MAX_TAX_LINES = 10
TEXT_LIMITS = {"supplier_name": 200, "supplier_tax_id": 32, "recipient_tax_id": 32, "invoice_number": 64}


# --- Lectura guardada (§5.3) ----------------------------------------------------------------------------------------------------


class TaxLine(BaseModel):
    vat_rate: str | None
    base_cents: int | None
    vat_cents: int | None


class Withholding(BaseModel):
    rate: str | None
    amount_cents: int | None


class DoubtfulField(BaseModel):
    field: DoubtField
    line_index: int | None
    reason: DoubtReason
    raw_text: str | None


class Extraction(BaseModel):
    """La lectura del agente ya normalizada. Es de solo lectura: la persona corrige en `Review`."""

    doc_type: DocType
    supplier_name: str | None
    supplier_tax_id: str | None
    recipient_tax_id: str | None
    invoice_number: str | None
    issue_date: date | None
    currency: str | None
    tax_breakdown: list[TaxLine]
    withholding: Withholding | None
    total_cents: int | None
    doubtful_fields: list[DoubtfulField]
    warnings: list[str]


# --- Correcciones de la persona (PUT /review) -----------------------------------------------------------------------------------


def _clean(value: Any, limit: int) -> Any:
    """Quita caracteres de control (un NUL rompería el `jsonb`) y espacios de sobra; lo vacío es `null`. La longitud la valida el campo."""
    if not isinstance(value, str):
        return value
    # Solo recorta lo desmesurado (4 veces el límite); si aun así pasa del límite, el campo lo rechaza.
    return clean_text(value, limit * 4)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewTaxLine(_Strict):
    vat_rate: Annotated[str, Field(pattern=RATE)] | None = None
    base_cents: Cents | None = None
    vat_cents: Cents | None = None


class ReviewWithholding(_Strict):
    rate: Annotated[str, Field(pattern=RATE)] | None = None
    amount_cents: Cents | None = None


class Review(_Strict):
    doc_type: DocType | None = None
    supplier_name: Annotated[str, Field(max_length=200)] | None = None
    supplier_tax_id: Annotated[str, Field(max_length=32)] | None = None
    recipient_tax_id: Annotated[str, Field(max_length=32)] | None = None
    invoice_number: Annotated[str, Field(max_length=64)] | None = None
    issue_date: date | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    tax_breakdown: Annotated[list[ReviewTaxLine], Field(max_length=MAX_TAX_LINES)] = Field(default_factory=list)
    withholding: ReviewWithholding | None = None
    total_cents: Cents | None = None

    @field_validator("supplier_name", "supplier_tax_id", "recipient_tax_id", "invoice_number", mode="before")
    @classmethod
    def _clean_text(cls, value: Any, info: ValidationInfo) -> Any:
        return _clean(value, TEXT_LIMITS[info.field_name or ""])

    @field_validator("issue_date", mode="before")
    @classmethod
    def _iso_date_only(cls, value: Any) -> Any:
        """`AAAA-MM-DD` y nada más: ni fecha con hora, ni marca de tiempo, ni fecha como número."""
        if value is None or isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str) and ISO_DATE.fullmatch(value):
            return value
        raise ValueError("La fecha debe tener la forma AAAA-MM-DD.")


# --- Respuestas -------------------------------------------------------------------------------------------------------------------


class DocumentError(BaseModel):
    code: FailureCodeName
    message: str


class DocumentSummary(BaseModel):
    """Una fila de la lista de Gastos."""

    id: UUID
    status: DocumentStatus
    original_filename: str
    mime_type: str
    created_at: datetime
    doc_type: DocType | None
    supplier_name: str | None
    total_cents: int | None
    doubtful_count: int
    injection_suspected: bool
    error: DocumentError | None


class Document(BaseModel):
    id: UUID
    status: DocumentStatus
    source: Literal["file", "camera"]
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    uploaded_at: datetime | None
    extracted_at: datetime | None
    updated_at: datetime
    extraction: Extraction | None
    review: Review | None
    injection_suspected: bool
    error: DocumentError | None
    # SPEC-W-003: las comprobaciones de lo guardado (nulo si no hay nada que comprobar o el documento no está en un estado registrable)
    # y el gasto vivo del documento (solo si está `registered`).
    validation: Validation | None
    expense_id: UUID | None


class DocumentState(BaseModel):
    id: UUID
    status: DocumentStatus


class UploadRequest(BaseModel):
    """`mime_type` es una cadena, no una enumeración: un tipo no permitido es un 415 propio, no un 422 genérico."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(ge=1, strict=True)
    source: Literal["file", "camera"]


class UploadInstructions(BaseModel):
    url: str
    method: Literal["PUT"]
    headers: dict[str, str]


class UploadResponse(BaseModel):
    id: UUID
    status: Literal["uploading"]
    upload: UploadInstructions
    max_bytes: int


class PreviewResponse(BaseModel):
    url: str
    expires_in: int
    previewable: bool
