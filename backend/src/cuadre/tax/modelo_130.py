"""Borrador del modelo 130 de un trimestre, acumulado desde el 1 de enero y casilla a casilla (SPEC-W-009 §5.1, RF-013, NFR-03 y NFR-08). Python puro.

Recibe facturas y gastos **ya leídos** y el «hoy», y devuelve las casillas 01 a 07 con los documentos que las componen. No lee la base de datos ni un reloj y
no guarda nada. Solo suma céntimos enteros; el único redondeo es el 20 % de la casilla 04, **una vez** sobre la 03 y con `ROUND_HALF_UP` (ADR-0006).

| Casilla | Es |
|---|---|
| 01 | suma de las bases de las facturas del periodo (todos los ámbitos; una rectificativa resta) |
| 02 | por gasto no anulado, su base más el IVA que NO se deduce (un gasto sin factura vale su importe) |
| 03 | 01 − 02 (puede ser negativa) |
| 04 | el 20 % de la 03, solo si es positiva |
| 05 | suma de los pagos de los trimestres anteriores del año; el de cada uno es `max(0, 07)` de ese trimestre |
| 06 | suma de las retenciones de las facturas (con signo) |
| 07 | 04 − 05 − 06 |

El periodo es del 1 de enero al último día del trimestre pedido, por fecha de expedición y fecha del gasto (D-02). Un resultado cero o negativo es «nada que
ingresar» y no se arrastra ni se compensa; si el periodo no tiene ningún documento, «sin actividad».
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

from cuadre.tax.limits import IRPF_PAYMENT_RATE, NOTE_130_70, NOTE_130_DRAFT, NOTE_130_EXCLUSIONS, YEAR_MAX_DOCUMENTS
from cuadre.tax.modelo_303 import QuarterTooLarge
from cuadre.tax.periods import deadline_status, filing_deadline, quarter_bounds, validate_period, year_start
from cuadre.tax.types_130 import Box130, CostRow, IncomeRow, Item130, Modelo130, ResultKind130
from cuadre.validators.vat import percentage_of


@dataclass(frozen=True, slots=True)
class _Figures:
    """Las siete casillas de un trimestre acumulado."""

    c01: int
    c02: int
    c03: int
    c04: int
    c05: int
    c06: int
    c07: int


def _cost(row: CostRow) -> int:
    """Lo que un gasto aporta a la 02: su base más el IVA que no se deduce."""
    return row.base_cents + (0 if row.deductible_vat else row.vat_cents)


def _figures(incomes: Sequence[IncomeRow], costs: Sequence[CostRow], previous_payments: Sequence[int]) -> _Figures:
    c01 = sum(income.base_cents for income in incomes)
    c02 = sum(_cost(cost) for cost in costs)
    c03 = c01 - c02
    c04 = percentage_of(c03, IRPF_PAYMENT_RATE) if c03 > 0 else 0
    c05 = sum(previous_payments)
    c06 = sum(income.irpf_cents for income in incomes)
    return _Figures(c01, c02, c03, c04, c05, c06, c04 - c05 - c06)


def _share(incomes: Sequence[IncomeRow], c01: int) -> int | None:
    """El porcentaje de la 01 que lleva retención (documentos con retención distinta de cero), al entero más cercano; `None` si la 01 no es positiva."""
    if c01 <= 0:
        return None
    withheld = sum(income.base_cents for income in incomes if income.irpf_cents != 0)
    with localcontext() as context:
        context.prec = 40
        return int((Decimal(withheld) * 100 / Decimal(c01)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _order(item: Item130) -> tuple[date, str, str]:
    return item.date, item.label, item.id


def build_modelo_130(
    year: int, quarter: int, incomes: Sequence[IncomeRow], costs: Sequence[CostRow], today: date
) -> Modelo130:
    """El 130 del trimestre. Filtra él mismo los documentos del 1 de enero al fin del trimestre (se le pueden pasar todos juntos). Falla con
    `InvalidPeriod`, `PeriodInFuture` o `QuarterTooLarge`."""
    validate_period(year, quarter, today)
    start = year_start(year)
    _, end = quarter_bounds(year, quarter)
    in_period = [income for income in incomes if start <= income.issue_date < end]
    spent = [cost for cost in costs if start <= cost.expense_date < end and not cost.voided]
    if len(in_period) + len(spent) > YEAR_MAX_DOCUMENTS:
        raise QuarterTooLarge("El periodo tiene más documentos de los que caben en el borrador.")

    # El pago de cada trimestre anterior, calculado con la misma regla sobre lo acumulado hasta su fin.
    payments: list[int] = []
    for earlier in range(1, quarter):
        _, earlier_end = quarter_bounds(year, earlier)
        figures = _figures(
            [income for income in in_period if income.issue_date < earlier_end],
            [cost for cost in spent if cost.expense_date < earlier_end],
            payments,
        )
        payments.append(max(0, figures.c07))
    total = _figures(in_period, spent, payments)

    invoice_items = tuple(
        sorted((Item130("invoice", i.id, i.label, i.issue_date, i.base_cents) for i in in_period), key=_order)
    )
    cost_items = tuple(sorted((Item130("expense", c.id, c.label, c.expense_date, _cost(c)) for c in spent), key=_order))
    withholding_items = tuple(
        sorted(
            (Item130("invoice", i.id, i.label, i.issue_date, i.irpf_cents) for i in in_period if i.irpf_cents != 0),
            key=_order,
        )
    )
    payment_items = tuple(
        Item130("quarter", f"T{k}", f"T{k} de {year}", quarter_bounds(year, k)[1] - timedelta(days=1), payments[k - 1])
        for k in range(1, quarter)
    )

    boxes = (
        Box130("01", "Ingresos computables", "rendimiento", total.c01, invoice_items, ()),
        Box130("02", "Gastos fiscalmente deducibles", "rendimiento", total.c02, cost_items, ()),
        Box130("03", "Rendimiento neto (01 − 02)", "rendimiento", total.c03, (), ("01", "02")),
        Box130("04", "20 % del rendimiento neto", "rendimiento", total.c04, (), ("03",)),
        Box130("05", "Pagos fraccionados de trimestres anteriores", "pagos", total.c05, payment_items, ()),
        Box130("06", "Retenciones soportadas", "pagos", total.c06, withholding_items, ()),
        Box130("07", "Pago fraccionado (04 − 05 − 06)", "resultado", total.c07, (), ("04", "05", "06")),
    )
    kind: ResultKind130
    if not in_period and not spent:
        kind = "sin_actividad"
    elif total.c07 > 0:
        kind = "a_ingresar"
    else:
        kind = "nada_que_ingresar"
    return Modelo130(
        year=year,
        quarter=quarter,
        period_start=start,
        period_end=end,
        deadline=filing_deadline(year, quarter),
        deadline_status=deadline_status(year, quarter, today),
        boxes=boxes,
        result_cents=total.c07,
        result_kind=kind,
        withheld_share_percent=_share(in_period, total.c01),
        notes=(NOTE_130_DRAFT, NOTE_130_EXCLUSIONS, NOTE_130_70),
    )
