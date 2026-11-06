"""IVA, retención y total (SPEC-W-003 §5.1, ADR-0006). Céntimos enteros y `Decimal` con `ROUND_HALF_UP`; ni un `float`.

Cada función devuelve el **motivo** en español por el que la comprobación falla, o `None` si pasa. Las tolerancias salen de `limits`.
"""

import re
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal

from cuadre.validators.limits import TOLERANCE_CENTS, VAT_RATE_MAX_EU, VAT_RATES_ES
from cuadre.validators.money import format_euros
from cuadre.validators.types import TaxLine, Withholding

# Igual que el patrón de los tipos en la lectura guardada. `[.]` y no un punto escapado; `fullmatch`, no `match`.
_RATE = re.compile(r"[0-9]{1,3}(?:[.][0-9]{1,2})?")

MISSING_LINES = "No se puede comprobar: faltan datos de las líneas de IVA."


def parse_rate(text: str | None) -> Decimal | None:
    """`21`, `21.00` y `7.5` son tipos; cualquier otra cosa, no."""
    if text is None or _RATE.fullmatch(text) is None:
        return None
    return Decimal(text)


def percentage_of(base_cents: int, rate: Decimal) -> int:
    """`base × tipo / 100` redondeado al céntimo, medio hacia arriba (ADR-0006)."""
    with localcontext() as context:
        context.prec = 40
        return int((Decimal(base_cents) * rate / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def lines_complete(lines: Sequence[TaxLine]) -> bool:
    return bool(lines) and all(
        line.vat_rate is not None and line.base_cents is not None and line.vat_cents is not None for line in lines
    )


def sums(lines: Sequence[TaxLine]) -> tuple[int, int]:
    """(suma de bases, suma de cuotas) de unas líneas completas."""
    return sum(line.base_cents or 0 for line in lines), sum(line.vat_cents or 0 for line in lines)


def rates_problem(lines: Sequence[TaxLine], scope: Literal["national", "eu"] | None) -> str | None:
    """Un proveedor español solo puede llevar los tipos de `VAT_RATES_ES`; uno de la UE, de 0 a `VAT_RATE_MAX_EU`. Con el ámbito sin
    determinar (el NIF no vale) se aplica lo español: es lo más estricto."""
    if not lines_complete(lines):
        return MISSING_LINES
    for number, line in enumerate(lines, start=1):
        rate = parse_rate(line.vat_rate)
        if rate is None:
            return f"El tipo de IVA de la línea {number} no es un número válido."
        if scope == "eu":
            if rate > VAT_RATE_MAX_EU:
                return f"El tipo del {line.vat_rate} % de la línea {number} supera el {VAT_RATE_MAX_EU} %."
        elif rate not in VAT_RATES_ES:
            return f"El tipo del {line.vat_rate} % de la línea {number} no es uno de los de España (0, 4, 10 o 21)."
    return None


def amounts_problem(lines: Sequence[TaxLine]) -> str | None:
    """Por línea, la cuota difiere del tipo como mucho `TOLERANCE_CENTS`."""
    if not lines_complete(lines):
        return MISSING_LINES
    for number, line in enumerate(lines, start=1):
        rate = parse_rate(line.vat_rate)
        if rate is None or line.base_cents is None or line.vat_cents is None:
            return MISSING_LINES
        expected = percentage_of(line.base_cents, rate)
        if abs(expected - line.vat_cents) > TOLERANCE_CENTS:
            return (
                f"En la línea {number}, el {line.vat_rate} % de {format_euros(line.base_cents)} da {format_euros(expected)} "
                f"y la cuota indicada es {format_euros(line.vat_cents)}."
            )
    return None


def withholding_problem(withholding: Withholding | None, lines: Sequence[TaxLine]) -> str | None:
    """Solo si hay retención: su importe es el porcentaje de la suma de bases, con la misma tolerancia."""
    if withholding is None:
        return None
    if withholding.rate is None or withholding.amount_cents is None:
        return "No se puede comprobar: faltan el porcentaje o el importe de la retención."
    rate = parse_rate(withholding.rate)
    if rate is None:
        return "El porcentaje de la retención no es un número válido."
    if not lines_complete(lines):
        return MISSING_LINES
    bases, _ = sums(lines)
    expected = percentage_of(bases, rate)
    if abs(expected - withholding.amount_cents) > TOLERANCE_CENTS:
        return (
            f"El {withholding.rate} % de la base ({format_euros(bases)}) da {format_euros(expected)} "
            f"y la retención indicada es {format_euros(withholding.amount_cents)}."
        )
    return None


def total_problem(lines: Sequence[TaxLine], withholding: Withholding | None, total_cents: int | None) -> str | None:
    """Base más IVA (menos la retención, si la hay) difiere del total como mucho `TOLERANCE_CENTS`."""
    if not lines_complete(lines) or total_cents is None:
        return "No se puede comprobar: faltan datos."
    if withholding is not None and withholding.amount_cents is None:
        return "No se puede comprobar: falta el importe retenido."
    bases, vats = sums(lines)
    retained = 0 if withholding is None else (withholding.amount_cents or 0)
    computed = bases + vats - retained
    if abs(computed - total_cents) > TOLERANCE_CENTS:
        what = "Base más IVA menos retención" if withholding is not None else "Base más IVA"
        return f"{what} da {format_euros(computed)} y el total indicado es {format_euros(total_cents)}."
    return None
