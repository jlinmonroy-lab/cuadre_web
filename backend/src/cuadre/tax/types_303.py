"""Tipos del modelo 303 (SPEC-W-008 §5.1). Inmutables y sin lógica: lo que entra (documentos ya leídos) y lo que sale (casillas con sus documentos)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from cuadre.tax.types import TaxTreatment

DeadlineStatus = Literal["en_curso", "plazo_abierto", "plazo_cerrado"]
ResultKind = Literal["a_ingresar", "a_compensar", "a_cero", "sin_actividad"]
BoxGroup = Literal["devengado", "deducible", "resultado", "adicional"]
Measure = Literal["base", "vat"]


@dataclass(frozen=True, slots=True)
class InvoiceRow:
    """Una factura emitida, tal como la guarda la base (una rectificativa lleva la diferencia, con signo, y el tipo y el tratamiento de la
    original). `label` es el número de factura que se enseña."""

    id: str
    label: str
    issue_date: date
    tax_treatment: TaxTreatment
    vat_rate: Decimal
    base_cents: int
    vat_cents: int


@dataclass(frozen=True, slots=True)
class ExpenseLine:
    """Una línea de IVA de un gasto, ya validada al registrarlo: el tipo, la base y la cuota."""

    vat_rate: Decimal
    base_cents: int
    vat_cents: int


@dataclass(frozen=True, slots=True)
class ExpenseRow:
    """Un gasto registrado. `label` es el proveedor; `voided` es `voided_at is not null`."""

    id: str
    label: str
    expense_date: date
    deductible_vat: bool
    voided: bool
    lines: tuple[ExpenseLine, ...]


@dataclass(frozen=True, slots=True)
class Item:
    """Un documento que compone una casilla, con la base y la cuota que aporta (negativas en una rectificativa)."""

    kind: Literal["invoice", "expense"]
    id: str
    label: str
    date: date
    base_cents: int
    vat_cents: int


@dataclass(frozen=True, slots=True)
class Box:
    """Una casilla. `measure` dice qué importe de cada item suma en ella (`base` o `vat`); las derivadas (27, 45 y 46) no tienen items y
    enumeran en `components` las casillas que las componen."""

    code: str
    label: str
    group: BoxGroup
    measure: Measure | None
    amount_cents: int
    items: tuple[Item, ...]
    components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Modelo303:
    year: int
    quarter: int
    period_start: date
    period_end: date  # exclusivo: el primer día del trimestre siguiente
    deadline: date
    deadline_status: DeadlineStatus
    boxes: tuple[Box, ...]
    result_cents: int
    result_kind: ResultKind
    notes: tuple[str, ...]
