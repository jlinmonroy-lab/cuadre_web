"""Importes de una factura y de una rectificativa (SPEC-W-007 §5.1.3 y §5.1.5, RES-02). Céntimos enteros; `Decimal` con `ROUND_HALF_UP`.

El redondeo es el de `cuadre.validators.vat.percentage_of` (SPEC-W-003, ADR-0006): una sola regla para los gastos y las facturas.

**Una rectificativa no calcula un porcentaje de un importe negativo**: eso desvía céntimos en cadenas de rectificaciones (una base de 105 al
10 % lleva 11 de IVA; anulada en dos pasos de −52 y −53 daría −5 y −5, y quedaría una cuota vigente de 1 con base 0). Como permite el art. 15.5
del Reglamento («los valores tras la rectificación»), sus cuotas son **las de la base corregida menos las vigentes**, siempre sobre una base ≥ 0.
"""

from decimal import Decimal

from cuadre.tax.limits import TWO_PLACES
from cuadre.tax.types import Amounts, InvoiceTerms, Standing
from cuadre.validators.vat import percentage_of


def _two(rate: Decimal) -> Decimal:
    return rate.quantize(TWO_PLACES)


def compute_amounts(
    terms: InvoiceTerms, base_cents: int, vat_rate: Decimal | None, irpf_rate: Decimal | None
) -> Amounts:
    """Los importes de una factura ordinaria. `vat_rate` solo cuenta si el tratamiento admite elegir IVA (si no, vale `0`); sin tipo elegido
    se usa el del tratamiento. `irpf_rate` solo cuenta si el tratamiento lleva retención y entonces es obligatorio."""
    if base_cents < 0:
        raise ValueError("La base de una factura ordinaria no es negativa.")
    vat = (vat_rate if vat_rate is not None else terms.vat_rate) if terms.vat_editable else Decimal(0)
    if terms.withholds:
        if irpf_rate is None:
            raise ValueError("Falta el tipo de retención de IRPF.")
        irpf = irpf_rate
    else:
        irpf = Decimal(0)
    vat_cents = percentage_of(base_cents, vat)
    irpf_cents = percentage_of(base_cents, irpf)
    return Amounts(base_cents, _two(vat), vat_cents, _two(irpf), irpf_cents, base_cents + vat_cents - irpf_cents)


def rectification_amounts(
    standing: Standing, vat_rate: Decimal, irpf_rate: Decimal, corrected_base_cents: int
) -> Amounts:
    """Los importes de una rectificativa: la diferencia entre los valores tras la rectificación (los de `corrected_base_cents`, con los tipos
    de la original) y los vigentes. Con la base corregida en 0 la rectificativa deja la factura entera en 0, también el IVA y la retención."""
    if corrected_base_cents < 0:
        raise ValueError("La base corregida no es negativa.")
    base = corrected_base_cents - standing.base_cents
    vat = percentage_of(corrected_base_cents, vat_rate) - standing.vat_cents
    irpf = percentage_of(corrected_base_cents, irpf_rate) - standing.irpf_cents
    return Amounts(base, _two(vat_rate), vat, _two(irpf_rate), irpf, base + vat - irpf)
