"""Modelos de la API del perfil, el logo y las series (SPEC-W-005 §5.3). De ellos sale el cliente TypeScript.

Los decimales (`irpf_rate`, `home_pct`) viajan como **cadenas** con patrón ASCII, nunca como `Decimal` de Pydantic (acepta números JSON,
notación científica y dígitos de otros alfabetos y haría que el cliente admitiera `number`: T5-01). Los modelos de entrada validan solo
la forma; la fiscalidad la valida `cuadre.profile`, que devuelve todos los errores a la vez.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

DECIMAL_PATTERN = r"^[0-9]{1,3}(\.[0-9]{1,2})?$"


class ProfileInput(BaseModel):
    """Los campos de §5.1. Los ausentes valen `null`. Los textos se validan en `cuadre.profile` (no aquí) para devolver todos los
    errores juntos y con sus mensajes."""

    model_config = ConfigDict(extra="forbid")

    legal_name: str | None = Field(default=None, max_length=1000)
    tax_id: str | None = Field(default=None, max_length=1000)
    fiscal_address: str | None = Field(default=None, max_length=2000)
    activity: str | None = Field(default=None, max_length=1000)
    iae_epigraph: str | None = Field(default=None, max_length=1000)
    activity_start_date: date | None = None
    vat_regime: str | None = Field(default=None, max_length=100)
    irpf_rate: str | None = Field(default=None, max_length=32)
    home_pct: str | None = Field(default=None, max_length=32)
    iban: str | None = Field(default=None, max_length=1000)


class MissingField(BaseModel):
    field: Literal["legal_name", "tax_id", "fiscal_address"]
    label: str


class Completeness(BaseModel):
    can_issue: bool
    missing_for_invoicing: list[MissingField]


class Retention(BaseModel):
    suggested_rate: Literal["7.00", "15.00"] | None
    reduced_until_year: int | None
    warning: str | None


class Profile(BaseModel):
    legal_name: str | None
    tax_id: str | None
    fiscal_address: str | None
    activity: str | None
    iae_epigraph: str | None
    activity_start_date: date | None
    vat_regime: Literal["general"]
    irpf_rate: Literal["7.00", "15.00"] | None
    home_pct: str | None = Field(pattern=DECIMAL_PATTERN)
    iban: str | None
    has_logo: bool
    updated_at: datetime
    completeness: Completeness
    retention: Retention


class LogoUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mime_type: str = Field(max_length=100)
    size_bytes: int = Field(ge=0, le=2**40)


class LogoUploadInstructions(BaseModel):
    url: str
    headers: dict[str, str]


class LogoUploadResponse(BaseModel):
    upload_id: UUID
    upload: LogoUploadInstructions


class LogoUrl(BaseModel):
    url: str
    expires_in: Literal[60] = 60


class InvoiceSeries(BaseModel):
    id: UUID
    code: str
    description: str | None
    first_number: int
    next_number: int
    is_default: bool
    archived: bool
    in_use: bool
    created_at: datetime


class SeriesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    first_number: StrictInt | None = None
    make_default: StrictBool = False


class SeriesUpdate(BaseModel):
    """Solo lo que cambia: una clave ausente no se toca y `description: null` la borra."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    first_number: StrictInt | None = None
    archived: StrictBool | None = None
