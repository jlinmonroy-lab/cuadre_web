"""Tipos de entrada y salida de los validadores (SPEC-W-003 §5.1 y §5.3).

Dataclasses inmutables y sin dependencias: ni Pydantic, ni base de datos, ni los modelos de `cuadre.documents`. La capa de la API convierte
(hito 3). `from_stored` lee la forma que se guarda en `documents.review` y `documents.extraction` (§5.3), así que quien llama solo pasa
`review` si existe y `extraction` si no.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from cuadre.validators.categories import ExpenseCategory

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class CheckCode(StrEnum):
    """Las comprobaciones, en el orden en que se muestran. Son una lista cerrada (§5.1)."""

    doc_type = "doc_type"
    required_data = "required_data"
    doubts_reviewed = "doubts_reviewed"
    supplier_tax_id = "supplier_tax_id"
    issue_date = "issue_date"
    currency = "currency"
    vat_rates = "vat_rates"
    vat_amounts = "vat_amounts"
    withholding = "withholding"
    total = "total"
    not_duplicate = "not_duplicate"


class WarningCode(StrEnum):
    """Avisos que nunca bloquean."""

    possible_duplicate = "possible_duplicate"
    recipient_mismatch = "recipient_mismatch"
    eu_supplier = "eu_supplier"


@dataclass(frozen=True, slots=True)
class TaxLine:
    vat_rate: str | None = None
    base_cents: int | None = None
    vat_cents: int | None = None


@dataclass(frozen=True, slots=True)
class Withholding:
    rate: str | None = None
    amount_cents: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class InvoiceData:
    """Lo que se registraría: `review` si existe y `extraction` si no. Todo puede faltar: eso es justo lo que se comprueba."""

    doc_type: str | None = None
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    recipient_tax_id: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    issue_date_malformed: bool = False  # había un texto y no era una fecha real (p. ej. 30 de febrero)
    currency: str | None = None
    tax_lines: tuple[TaxLine, ...] = ()
    withholding: Withholding | None = None
    total_cents: int | None = None


@dataclass(frozen=True, slots=True)
class ExistingExpense:
    """Un gasto **no anulado** de la misma persona: lo que hace falta para detectar duplicados."""

    supplier_tax_id: str | None
    invoice_number_key: str | None
    expense_date: date
    total_cents: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationContext:
    """Lo que no sale del documento. `today` ya viene calculado en Europe/Madrid: los validadores no miran ningún reloj."""

    today: date
    owner_tax_id: str | None = None  # `business_profiles.tax_id`, tal cual
    existing: tuple[ExistingExpense, ...] = ()
    has_review: bool = False
    doubtful_count: int = 0
    injection_suspected: bool = False


@dataclass(frozen=True, slots=True)
class Check:
    code: CheckCode
    label: str
    status: Literal["ok", "failed"]
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True, slots=True)
class ValidationWarning:
    code: WarningCode
    message: str


@dataclass(frozen=True, slots=True)
class Preview:
    supplier_scope: Literal["national", "eu"] | None
    deductible_vat: bool
    deductible_note: str | None
    suggested_category: ExpenseCategory


@dataclass(frozen=True, slots=True)
class RegistrableValues:
    """Los valores ya normalizados que recibirá `app.register_expense_from_document`. Solo existen si todas las comprobaciones pasan."""

    expense_date: date
    supplier_name: str
    supplier_tax_id: str
    supplier_scope: Literal["national", "eu"]
    invoice_number: str | None
    invoice_number_key: str | None
    doc_type: str
    base_cents: int
    vat_cents: int
    withholding_cents: int
    total_cents: int
    tax_lines: tuple[TaxLine, ...]
    deductible_vat: bool


@dataclass(frozen=True, slots=True)
class Validation:
    can_register: bool
    requires_acknowledgement: bool
    checks: tuple[Check, ...]
    warnings: tuple[ValidationWarning, ...]
    preview: Preview
    values: RegistrableValues | None


# --- Lectura de la forma guardada ------------------------------------------------------------------------------------------------


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _date(value: object) -> tuple[date | None, bool]:
    """(fecha, malformada). Una fecha ausente no es malformada; un texto que no es una fecha real, sí."""
    if value is None or value == "":
        return None, False
    if isinstance(value, datetime):
        return None, True
    if isinstance(value, date):
        return value, False
    if isinstance(value, str) and _ISO_DATE.fullmatch(value) is not None:
        try:
            return date.fromisoformat(value), False
        except ValueError:
            return None, True
    return None, True


def _lines(value: object) -> tuple[TaxLine, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    lines = []
    for item in value:
        if isinstance(item, Mapping):
            lines.append(
                TaxLine(_text(item.get("vat_rate")), _int(item.get("base_cents")), _int(item.get("vat_cents")))
            )
        else:
            lines.append(TaxLine())  # una entrada que no es un objeto cuenta como una línea sin datos
    return tuple(lines)


def from_stored(shown: Mapping[str, Any]) -> InvoiceData:
    """Lee `review` o `extraction` (§5.3). Tolera claves ausentes y valores de otro tipo: lo que no se entiende queda en `None`."""
    issue_date, malformed = _date(shown.get("issue_date"))
    raw_withholding = shown.get("withholding")
    withholding = (
        Withholding(_text(raw_withholding.get("rate")), _int(raw_withholding.get("amount_cents")))
        if isinstance(raw_withholding, Mapping)
        else None
    )
    return InvoiceData(
        doc_type=_text(shown.get("doc_type")),
        supplier_name=_text(shown.get("supplier_name")),
        supplier_tax_id=_text(shown.get("supplier_tax_id")),
        recipient_tax_id=_text(shown.get("recipient_tax_id")),
        invoice_number=_text(shown.get("invoice_number")),
        issue_date=issue_date,
        issue_date_malformed=malformed,
        currency=_text(shown.get("currency")),
        tax_lines=_lines(shown.get("tax_breakdown")),
        withholding=withholding,
        total_cents=_int(shown.get("total_cents")),
    )
