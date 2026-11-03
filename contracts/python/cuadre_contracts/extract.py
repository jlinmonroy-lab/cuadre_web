"""Contrato 1 · Lectura de facturas de compra: POST {AGENTS_BASE_URL}/v1/extract.

El servicio de agentes SOLO extrae. No valida NIF, sumas, tipos de IVA ni duplicados, y no
registra nada: eso vive en cuadre-web (RES-01). Todo escalar que no se lee con claridad
viaja como `null` y se lista en `doubtful_fields`.
"""

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import Field, HttpUrl

from .common import Amount, ContractModel, Cost, Currency, Locale, Rate, ResponseModel


class MimeType(StrEnum):
    pdf = "application/pdf"
    jpeg = "image/jpeg"
    png = "image/png"
    heic = "image/heic"
    webp = "image/webp"


class DocType(StrEnum):
    full_invoice = "full_invoice"
    simplified_invoice = "simplified_invoice"
    ticket = "ticket"
    receipt = "receipt"
    other = "other"
    not_an_invoice = "not_an_invoice"


class ExtractedField(StrEnum):
    doc_type = "doc_type"
    supplier_name = "supplier_name"
    supplier_tax_id = "supplier_tax_id"
    recipient_tax_id = "recipient_tax_id"
    invoice_number = "invoice_number"
    issue_date = "issue_date"
    currency = "currency"
    tax_breakdown = "tax_breakdown"
    withholding = "withholding"
    total = "total"


class DoubtReason(StrEnum):
    illegible = "illegible"
    ambiguous = "ambiguous"
    missing = "missing"
    inconsistent = "inconsistent"


class ExtractRequest(ContractModel):
    document_id: UUID = Field(description="Identificador del documento en cuadre-web. Se devuelve en la traza.")
    document_url: HttpUrl = Field(
        description="URL firmada y de corta duración (unos 120 s) del archivo en Storage. No debe registrarse en logs."
    )
    mime_type: MimeType
    locale: Locale = "es-ES"


class TaxLine(ContractModel):
    vat_rate: Rate | None = Field(description="Tipo de IVA de la línea; null si no se lee.")
    base: Amount | None = Field(description="Base imponible de la línea.")
    vat_amount: Amount | None = Field(description="Cuota de IVA de la línea.")


class Withholding(ContractModel):
    rate: Rate | None = Field(description="Porcentaje de retención de IRPF.")
    amount: Amount | None = Field(description="Importe retenido.")


class DoubtfulField(ContractModel):
    field: ExtractedField
    line_index: int | None = Field(
        default=None, ge=0, description="Posición en tax_breakdown cuando la duda afecta a una línea concreta."
    )
    reason: DoubtReason
    raw_text: str | None = Field(
        default=None, max_length=200, description="Texto tal como se leyó, para ayudar a la revisión. Nunca un IBAN."
    )


class ExtractedInvoice(ResponseModel):
    doc_type: DocType
    supplier_name: str | None
    supplier_tax_id: str | None = Field(description="NIF/CIF/NIF-IVA del proveedor tal como aparece. Sin normalizar.")
    recipient_tax_id: str | None = Field(
        description="NIF del destinatario si aparece; sirve para decidir la deducibilidad de las simplificadas."
    )
    invoice_number: str | None
    issue_date: date | None
    currency: Currency | None
    tax_breakdown: list[TaxLine] = Field(default_factory=list, description="Desglose de IVA, una línea por tipo.")
    withholding: Withholding | None = Field(
        default=None, description="Retención de IRPF. null cuando la factura no la lleva."
    )
    total: Amount | None
    doubtful_fields: list[DoubtfulField] = Field(default_factory=list)
    injection_suspected: bool = Field(
        default=False,
        description=(
            "El documento contiene texto que parece una instrucción dirigida a un sistema. Es solo una señal: "
            "cuadre-web fuerza la revisión manual, pero nunca depende de ella para validar."
        ),
    )
    warnings: list[str] = Field(default_factory=list, description="Avisos en lenguaje natural, para la persona.")


class Usage(ResponseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_eur: Cost | None = None


class ExtractResponse(ResponseModel):
    extraction: ExtractedInvoice
    usage: Usage
    trace_id: str = Field(description="Identificador de traza del servicio de agentes.")


class AgentErrorCode(StrEnum):
    unreadable = "unreadable"
    unsupported_media_type = "unsupported_media_type"
    payload_too_large = "payload_too_large"
    invalid_request = "invalid_request"
    unauthorized = "unauthorized"
    upstream_error = "upstream_error"


class AgentError(ResponseModel):
    code: AgentErrorCode
    message: str
    trace_id: str | None = None
