"""Lo vigente de una factura tras sus rectificativas (SPEC-W-007 §5.1.5, D-12). Python puro."""

from collections.abc import Sequence

from cuadre.tax.types import Amounts, Standing


def standing_of(original: Amounts, rectifications: Sequence[Amounts]) -> Standing:
    """La base, el IVA y la retención vigentes: los de la original más las diferencias de cada rectificativa (con su signo)."""
    return Standing(
        base_cents=original.base_cents + sum(r.base_cents for r in rectifications),
        vat_cents=original.vat_cents + sum(r.vat_cents for r in rectifications),
        irpf_cents=original.irpf_cents + sum(r.irpf_cents for r in rectifications),
    )
