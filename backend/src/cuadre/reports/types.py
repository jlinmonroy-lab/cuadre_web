"""Tipos del reporte mensual (SPEC-W-013 §5.1 y §5.4). Inmutables y sin lógica.

Todos los importes son céntimos enteros; las variaciones y las cuotas, puntos básicos enteros (1 pb = 0,01 %). Nada de `float` (RES-02).
"""

from dataclasses import dataclass
from typing import Literal

from cuadre.closing.types import Scope
from cuadre.validators.categories import ExpenseCategory

MonthStatus = Literal["closed", "in_progress", "pending"]


@dataclass(frozen=True, slots=True)
class CategorisedExpense:
    """Un gasto con su categoría. `voided` es `voided_at is not null`; los manuales no llevan IVA."""

    id: str
    category: ExpenseCategory
    base_cents: int
    vat_cents: int
    deductible_vat: bool
    voided: bool


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    """Lo gastado en una categoría durante el mes: base más IVA no deducible de sus gastos vivos."""

    category: ExpenseCategory
    label: str
    expenses_cents: int
    expense_count: int


@dataclass(frozen=True, slots=True)
class ScopeShare:
    """Lo facturado en un ámbito y su cuota sobre el total del mes (`None` si no tiene sentido, D-06)."""

    scope: Scope
    base_cents: int
    share_bp: int | None


@dataclass(frozen=True, slots=True)
class MonthFigures:
    """Las cifras de un mes que entran en una comparación: las mismas que enseña `/mensual`."""

    year: int
    month: int
    status: MonthStatus
    total_cents: int
    expenses_cents: int


@dataclass(frozen=True, slots=True)
class Comparison:
    """El mes frente al anterior (D-05). Las variaciones son `None` si el importe anterior no es mayor que 0."""

    previous_year: int
    previous_month: int
    previous_status: MonthStatus
    total_cents: int
    expenses_cents: int
    result_cents: int
    total_delta_cents: int
    expenses_delta_cents: int
    result_delta_cents: int
    total_variation_bp: int | None
    expenses_variation_bp: int | None
