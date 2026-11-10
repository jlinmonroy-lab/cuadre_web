"""Modelos de la API de facturas (SPEC-W-007 §5.3). De ellos sale el cliente TypeScript.

La **entrada es suelta** (Anexo B.1-D y B.1-F): `str` con `max_length`, sin `Literal` ni patrón y con `extra="forbid"`. Una fecha `2026-02-30` o un
cliente `no-uuid` llegan al dominio y salen en `invalid_invoice` con **todos los errores a la vez**; si se declararan con un tipo estricto, Pydantic
respondería un `validation_error` por separado. `base_cents` va con `StrictInt`: un `int` normal acepta `true`, `"120"`, `120.0` y `1e3` sin avisar.
Importes siempre `int` de céntimos y tipos como cadenas `"21.00"`: ningún `float` (RES-02). La salida sí lleva uniones de literales.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

Scope = Literal["national", "eu", "non_eu"]
ClientKind = Literal["business", "individual"]
InvoiceKind = Literal["standard", "rectifying"]
TaxTreatment = Literal[
    "national_vat", "eu_reverse_charge", "eu_consumer_vat", "non_eu_consumer_vat", "non_eu_not_subject"
]


class InvoiceInput(BaseModel):
    """Los campos de §5.1.1. Los ausentes valen `null` y el dominio dice cuáles hacen falta; `series_id` vacío es la serie predeterminada."""

    model_config = ConfigDict(extra="forbid")

    client_id: str | None = Field(default=None, max_length=100)
    series_id: str | None = Field(default=None, max_length=100)
    issue_date: str | None = Field(default=None, max_length=100)
    concept: str | None = Field(default=None, max_length=2000)
    base_cents: StrictInt | None = None
    vat_rate: str | None = Field(default=None, max_length=100)


class RectificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=2000)
    corrected_base_cents: StrictInt | None = None
    issue_date: str | None = Field(default=None, max_length=100)


class PaymentInput(BaseModel):
    """`paid` va con `StrictBool`: un `"yes"` no es `true`."""

    model_config = ConfigDict(extra="forbid")

    paid: StrictBool


class InvoiceClient(BaseModel):
    """La copia del cliente que la factura congeló al emitirse (D-09)."""

    id: UUID
    name: str
    kind: ClientKind
    country: str
    scope: Scope
    tax_id: str | None
    address: str


class InvoiceRef(BaseModel):
    id: UUID
    display_number: str
    issue_date: date


class Standing(BaseModel):
    """Lo vigente de una factura tras sus rectificativas (§5.1.5)."""

    base_cents: int
    vat_cents: int
    irpf_cents: int


class Invoice(BaseModel):
    id: UUID
    series_code: str
    number: int
    display_number: str
    kind: InvoiceKind
    issue_date: date
    client: InvoiceClient
    concept: str
    tax_treatment: TaxTreatment
    base_cents: int
    vat_rate: str
    vat_cents: int
    irpf_rate: str
    irpf_cents: int
    total_cents: int
    legal_note: str | None
    rectifies: InvoiceRef | None
    rectification_reason: str | None
    rectified_by: list[str]
    standing: Standing | None
    paid_at: datetime | None
    pdf_status: Literal["ready", "pending"]
    created_at: datetime


class InvoicePreview(BaseModel):
    """Lo que se emitiría, sin número ni nada escrito (§5.3). El navegador lo enseña y no calcula impuestos."""

    scope: Scope
    kind: ClientKind
    tax_treatment: TaxTreatment
    base_cents: int
    vat_rate: str
    vat_cents: int
    irpf_rate: str
    irpf_cents: int
    total_cents: int
    legal_note: str | None
    vat_editable: bool


class ClientBilling(BaseModel):
    """Lo facturado a un cliente en un año: la suma de las bases con signo (las rectificativas restan)."""

    client_id: UUID
    billed_cents: int
