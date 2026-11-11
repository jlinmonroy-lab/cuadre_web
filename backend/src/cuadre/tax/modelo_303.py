"""Borrador del modelo 303 de un trimestre, casilla a casilla (SPEC-W-008 §5.1, RF-013, NFR-03 y NFR-08). Python puro.

Recibe facturas y gastos **ya leídos** y el «hoy», y devuelve las casillas del régimen general con los documentos que las componen. No lee la
base de datos ni un reloj, no redondea nada (las cuotas de cada documento ya están redondeadas al céntimo al emitir o registrar: D-05) y no
guarda nada. Todo son sumas de céntimos enteros.

| Documento | Va a |
|---|---|
| Factura con IVA (`national_vat`, `eu_consumer_vat`, `non_eu_consumer_vat`) al 4, 10 o 21 % | base y cuota de 01-03, 04-06 o 07-09 |
| `eu_reverse_charge` | 59 (base) |
| `non_eu_not_subject` | 120 (base) |
| Gasto no anulado con IVA deducible | 28 (base) y 29 (cuota) de sus líneas con tipo > 0 |

Una rectificativa es una factura más con importes negativos; cuenta en el trimestre de **su** fecha de expedición (D-02). El resultado es
`46 = 27 − 45`: positivo «a ingresar», negativo «a compensar» (sin compensar nada), cero «a cero» y, si el trimestre no tiene ningún
documento, «sin actividad».
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from cuadre.tax.limits import (
    NOTE_303_349,
    NOTE_303_CANARIAS,
    NOTE_303_DRAFT,
    NOTE_303_EXCLUSIONS,
    QUARTER_MAX_DOCUMENTS,
    VAT_RATES,
    VAT_TREATMENTS,
)
from cuadre.tax.periods import deadline_status, filing_deadline, quarter_bounds, validate_period
from cuadre.tax.types_303 import Box, BoxGroup, ExpenseRow, InvoiceRow, Item, Measure, Modelo303, ResultKind

# Casilla de base y de cuota de cada tipo de IVA.
_RATE_BOXES = {Decimal(4): ("01", "03"), Decimal(10): ("04", "06"), Decimal(21): ("07", "09")}
assert set(_RATE_BOXES) == set(VAT_RATES)


@dataclass(frozen=True, slots=True)
class _BoxSpec:
    code: str
    label: str
    group: BoxGroup
    measure: Measure | None
    components: tuple[str, ...] = ()


# El orden es el de la pantalla (el del prototipo).
_BOXES = (
    _BoxSpec("01", "Base imponible al 4 %", "devengado", "base"),
    _BoxSpec("03", "Cuota al 4 %", "devengado", "vat"),
    _BoxSpec("04", "Base imponible al 10 %", "devengado", "base"),
    _BoxSpec("06", "Cuota al 10 %", "devengado", "vat"),
    _BoxSpec("07", "Base imponible al 21 %", "devengado", "base"),
    _BoxSpec("09", "Cuota al 21 %", "devengado", "vat"),
    _BoxSpec("27", "Total cuota devengada", "devengado", None, ("03", "06", "09")),
    _BoxSpec("28", "Base de operaciones interiores corrientes", "deducible", "base"),
    _BoxSpec("29", "Cuota deducible", "deducible", "vat"),
    _BoxSpec("45", "Total a deducir", "deducible", None, ("29",)),
    _BoxSpec("46", "Resultado del régimen general (27 − 45)", "resultado", None, ("27", "45")),
    _BoxSpec("59", "Servicios a empresas de la UE", "adicional", "base"),
    _BoxSpec("120", "Operaciones no sujetas por reglas de localización", "adicional", "base"),
)


class UnsupportedVatRate(ValueError):
    """Un documento trae un tipo de IVA que no existe para su tratamiento: no se esconde en otra casilla. Sin datos del documento en el mensaje."""

    code = "unsupported_vat_rate"


class QuarterTooLarge(ValueError):
    """El trimestre tiene más documentos de los que caben en una respuesta (ADR-0016)."""

    code = "quarter_too_large"


def _invoice_boxes(invoice: InvoiceRow) -> tuple[str, str | None]:
    """La casilla de base y, si la hay, la de cuota de una factura."""
    treatment = invoice.tax_treatment
    if treatment in ("eu_reverse_charge", "non_eu_not_subject"):
        if invoice.vat_rate != 0 or invoice.vat_cents != 0:
            raise UnsupportedVatRate("Una operación sin IVA lleva un tipo o una cuota distintos de cero.")
        return ("59" if treatment == "eu_reverse_charge" else "120"), None
    if treatment not in VAT_TREATMENTS:
        raise ValueError(f"Tratamiento fiscal desconocido: {treatment!r}")
    boxes = _RATE_BOXES.get(invoice.vat_rate)
    if boxes is None:
        raise UnsupportedVatRate("El tipo de IVA de una factura no es el 4, el 10 ni el 21 %.")
    return boxes


def _order(item: Item) -> tuple[date, str, str]:
    return item.date, item.label, item.id


def build_modelo_303(
    year: int, quarter: int, invoices: Sequence[InvoiceRow], expenses: Sequence[ExpenseRow], today: date
) -> Modelo303:
    """El 303 del trimestre. Filtra él mismo los documentos que caen en el trimestre (fecha de expedición o del gasto), de modo que se le pueden
    pasar todos juntos. Falla con `InvalidPeriod`, `PeriodInFuture`, `UnsupportedVatRate` o `QuarterTooLarge`."""
    validate_period(year, quarter, today)
    start, end = quarter_bounds(year, quarter)
    in_quarter = [i for i in invoices if start <= i.issue_date < end]
    spent = [e for e in expenses if start <= e.expense_date < end and not e.voided]
    if len(in_quarter) + len(spent) > QUARTER_MAX_DOCUMENTS:
        raise QuarterTooLarge("El trimestre tiene más documentos de los que caben en el borrador.")

    items: dict[str, list[Item]] = {spec.code: [] for spec in _BOXES}
    for invoice in in_quarter:
        base_box, vat_box = _invoice_boxes(invoice)
        item = Item("invoice", invoice.id, invoice.label, invoice.issue_date, invoice.base_cents, invoice.vat_cents)
        items[base_box].append(item)
        if vat_box is not None:
            items[vat_box].append(item)
    for expense in spent:
        if not expense.deductible_vat:
            continue
        counted = [line for line in expense.lines if line.vat_rate > 0]
        if not counted:
            continue
        item = Item(
            "expense",
            expense.id,
            expense.label,
            expense.expense_date,
            sum(line.base_cents for line in counted),
            sum(line.vat_cents for line in counted),
        )
        items["28"].append(item)
        items["29"].append(item)

    amounts: dict[str, int] = {}
    for spec in _BOXES:
        if spec.measure == "base":
            amounts[spec.code] = sum(item.base_cents for item in items[spec.code])
        elif spec.measure == "vat":
            amounts[spec.code] = sum(item.vat_cents for item in items[spec.code])
    amounts["27"] = amounts["03"] + amounts["06"] + amounts["09"]
    amounts["45"] = amounts["29"]
    amounts["46"] = amounts["27"] - amounts["45"]

    boxes = tuple(
        Box(
            spec.code,
            spec.label,
            spec.group,
            spec.measure,
            amounts[spec.code],
            tuple(sorted(items[spec.code], key=_order)),
            spec.components,
        )
        for spec in _BOXES
    )
    result = amounts["46"]
    kind: ResultKind
    if not in_quarter and not spent:
        kind = "sin_actividad"
    elif result > 0:
        kind = "a_ingresar"
    elif result < 0:
        kind = "a_compensar"
    else:
        kind = "a_cero"
    notes = (NOTE_303_DRAFT, NOTE_303_EXCLUSIONS, NOTE_303_CANARIAS) + ((NOTE_303_349,) if amounts["59"] != 0 else ())
    return Modelo303(
        year=year,
        quarter=quarter,
        period_start=start,
        period_end=end,
        deadline=filing_deadline(year, quarter),
        deadline_status=deadline_status(year, quarter, today),
        boxes=boxes,
        result_cents=result,
        result_kind=kind,
        notes=notes,
    )
