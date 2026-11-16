"""Reglas del reporte mensual (SPEC-W-013 §5.1, D-03 a D-08). Python puro: sin base de datos, sin reloj y solo con enteros.

Todo lo que decide una cifra del reporte vive aquí, con enteros: el coste de un gasto (la misma regla que el cierre), la variación y las cuotas en puntos básicos
(redondeo *half-up* sobre el valor absoluto, con el signo del cambio), el desglose por categoría, la ventana de la tendencia, la comparación con el mes anterior
y el aviso de descuadre. La interfaz solo las escribe.
"""

from collections.abc import Iterable
from typing import Any

from cuadre.closing.limits import CLOSING_MAX_DOCUMENTS, MAX_WINDOW_MONTHS, WINDOW_MONTHS
from cuadre.closing.rules import InvalidMonth
from cuadre.closing.types import SCOPES, YearMonth
from cuadre.reports.types import CategorisedExpense, CategoryTotal, Comparison, MonthFigures, ScopeShare
from cuadre.validators.categories import LABELS, ExpenseCategory

BASIS_POINTS = 10_000

# Texto fijo (sin importes ni nombres de la persona): D-04. La interfaz lo enseña tal cual cuando las categorías no cuadran con el cierre.
EXPENSES_NOTE = (
    "El desglose por categoría se calcula con los gastos de hoy y no coincide con el cierre de este mes: se registró o se anuló algún gasto "
    "después de cerrarlo. El cierre se actualizará en su próxima ejecución."
)


class ReportTooLarge(ValueError):
    """Hay más gastos de los que caben en un reporte."""

    code = "report_too_large"


class PeriodBeforeActivity(ValueError):
    """El mes pedido es anterior al primer mes con actividad de la persona: no se muestra."""

    code = "closing_not_found"


def _whole(value: Any, what: str) -> int:
    """Un importe en céntimos: un entero de verdad (ni `bool`, ni decimal, ni texto)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} debe ser un entero en céntimos.")
    return value


def _half_up(numerator: int, denominator: int) -> int:
    """`numerator / denominator` redondeado al entero más cercano; el medio se aleja de cero (*half-up* sobre el valor absoluto). `denominator > 0`."""
    magnitude = (2 * abs(numerator) + denominator) // (2 * denominator)
    return -magnitude if numerator < 0 else magnitude


# --- Importes ---------------------------------------------------------------------------------------------------------------------------


def expense_cost(base_cents: int, vat_cents: int, deductible_vat: bool) -> int:
    """Lo que cuenta un gasto: su base más su IVA si no es deducible. Es la regla del cierre mensual (SPEC-W-012 D-02)."""
    base = _whole(base_cents, "La base del gasto")
    vat = _whole(vat_cents, "El IVA del gasto")
    return base + (0 if deductible_vat else vat)


def variation_bp(current_cents: int, previous_cents: int) -> int | None:
    """La variación de `current` frente a `previous` en puntos básicos; `None` si `previous` no es mayor que 0 (no hay referencia, D-05)."""
    current = _whole(current_cents, "El importe actual")
    previous = _whole(previous_cents, "El importe anterior")
    if previous <= 0:
        return None
    return _half_up((current - previous) * BASIS_POINTS, previous)


def share_bp(base_cents: int, total_cents: int) -> int | None:
    """La cuota de `base` sobre `total` en puntos básicos; `None` si el total no es mayor que 0 o la base es negativa (D-06)."""
    base = _whole(base_cents, "La base del ámbito")
    total = _whole(total_cents, "El total del mes")
    if total <= 0 or base < 0:
        return None
    return _half_up(base * BASIS_POINTS, total)


def scope_shares(national_cents: int, eu_cents: int, non_eu_cents: int) -> tuple[ScopeShare, ...]:
    """Los tres ámbitos, siempre en el orden nacional, UE y fuera de la UE, con su cuota sobre el total del mes."""
    bases = {"national": national_cents, "eu": eu_cents, "non_eu": non_eu_cents}
    total = sum(_whole(value, "La base del ámbito") for value in bases.values())
    return tuple(
        ScopeShare(scope=scope, base_cents=bases[scope], share_bp=share_bp(bases[scope], total)) for scope in SCOPES
    )


# --- Gastos por categoría ---------------------------------------------------------------------------------------------------------------


def group_by_category(expenses: Iterable[CategorisedExpense]) -> tuple[CategoryTotal, ...]:
    """El gasto del mes por categoría (D-03): solo los gastos vivos, solo las categorías con importe distinto de 0, de mayor a menor y, a igualdad, por etiqueta."""
    documents = list(expenses)
    if len(documents) > CLOSING_MAX_DOCUMENTS:
        raise ReportTooLarge("Hay más gastos de los que caben en un reporte.")
    totals: dict[ExpenseCategory, list[int]] = {}
    for expense in documents:
        if expense.voided:
            continue
        category = ExpenseCategory(expense.category)  # una categoría que no existe es un error, no un «otros»
        entry = totals.setdefault(category, [0, 0])
        entry[0] += expense_cost(expense.base_cents, expense.vat_cents, expense.deductible_vat)
        entry[1] += 1
    grouped = (
        CategoryTotal(category=category, label=LABELS[category], expenses_cents=cents, expense_count=count)
        for category, (cents, count) in totals.items()
        if cents != 0
    )
    return tuple(sorted(grouped, key=lambda item: (-item.expenses_cents, item.label)))


def expenses_note(category_total_cents: int, month_expenses_cents: int) -> str | None:
    """El aviso de descuadre (D-04): `None` si el desglose suma lo mismo que los gastos del mes."""
    if _whole(category_total_cents, "El total por categoría") == _whole(month_expenses_cents, "Los gastos del mes"):
        return None
    return EXPENSES_NOTE


# --- Tendencia y comparación ------------------------------------------------------------------------------------------------------------


def trend_window(selected: YearMonth, first: YearMonth | None, months: int = WINDOW_MONTHS) -> tuple[YearMonth, ...]:
    """Los meses de la tendencia (D-07): los `months` que terminan en `selected`, sin pasar del primer mes con actividad (`None`: solo `selected`).

    Falla con `PeriodBeforeActivity` si `selected` es anterior a `first`: ese mes no se muestra.
    """
    if isinstance(months, bool) or not 1 <= months <= MAX_WINDOW_MONTHS:
        raise ValueError(f"La tendencia admite de 1 a {MAX_WINDOW_MONTHS} meses.")
    if first is None:
        return (selected,)
    if selected < first:
        raise PeriodBeforeActivity("Ese mes es anterior a la primera actividad de la cuenta.")
    start = max(first, selected.shift(-(months - 1)))
    window: list[YearMonth] = []
    month = start
    while month <= selected:
        window.append(month)
        month = month.next()
    return tuple(window)


def build_comparison(current: MonthFigures, previous: MonthFigures | None) -> Comparison | None:
    """El mes frente al anterior (D-05); `None` si no hay mes anterior que mostrar."""
    if previous is None:
        return None
    current_result = current.total_cents - current.expenses_cents
    previous_result = previous.total_cents - previous.expenses_cents
    return Comparison(
        previous_year=previous.year,
        previous_month=previous.month,
        previous_status=previous.status,
        total_cents=previous.total_cents,
        expenses_cents=previous.expenses_cents,
        result_cents=previous_result,
        total_delta_cents=current.total_cents - previous.total_cents,
        expenses_delta_cents=current.expenses_cents - previous.expenses_cents,
        result_delta_cents=current_result - previous_result,
        total_variation_bp=variation_bp(current.total_cents, previous.total_cents),
        expenses_variation_bp=variation_bp(current.expenses_cents, previous.expenses_cents),
    )


def quarter_of(month: int) -> int:
    """El trimestre natural (1 a 4) de un mes (1 a 12)."""
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise InvalidMonth("El mes debe estar entre 1 y 12.")
    return (month - 1) // 3 + 1
