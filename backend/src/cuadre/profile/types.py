"""Tipos del dominio del perfil (SPEC-W-005 §5.3). Inmutables y sin lógica."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RawProfile:
    """Lo que llega de la API, sin fiarse de nada: cada campo es `object` y un tipo inesperado es un error de campo, no una excepción.
    `irpf_rate` y `home_pct` llegan como cadenas (`"7.00"`); `activity_start_date` como `date`."""

    legal_name: object = None
    tax_id: object = None
    fiscal_address: object = None
    activity: object = None
    iae_epigraph: object = None
    activity_start_date: object = None
    vat_regime: object = None
    irpf_rate: object = None
    home_pct: object = None
    iban: object = None


@dataclass(frozen=True, slots=True)
class ProfileValues:
    """El perfil validado y normalizado, listo para guardarse. El NIF es la clave compacta; el IBAN, el compacto en mayúsculas."""

    legal_name: str | None
    tax_id: str | None
    fiscal_address: str | None
    activity: str | None
    iae_epigraph: str | None
    activity_start_date: date | None
    vat_regime: str
    irpf_rate: Decimal | None
    home_pct: Decimal | None
    iban: str | None


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ProfileResult:
    """O los valores, o **todos** los errores a la vez (nunca los dos)."""

    values: ProfileValues | None
    errors: tuple[FieldError, ...]


@dataclass(frozen=True, slots=True)
class StoredIdentity:
    """Los tres campos guardados que deciden si se puede emitir."""

    legal_name: object = None
    tax_id: object = None
    fiscal_address: object = None


@dataclass(frozen=True, slots=True)
class Missing:
    field: str
    label: str


@dataclass(frozen=True, slots=True)
class Completeness:
    can_issue: bool
    missing_for_invoicing: tuple[Missing, ...]


@dataclass(frozen=True, slots=True)
class Retention:
    suggested_rate: str | None
    reduced_until_year: int | None
    warning: str | None


@dataclass(frozen=True, slots=True)
class SeriesResult:
    """El código, la descripción y el número inicial validados, o todos los errores."""

    code: str | None
    description: str | None
    first_number: int | None
    errors: tuple[FieldError, ...]
