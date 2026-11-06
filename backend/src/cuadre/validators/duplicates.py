"""Duplicados (SPEC-W-003 §5.1, D-04).

**Duro:** mismo NIF del proveedor y mismo número de factura, normalizados, entre los gastos no anulados. Lo hace cumplir también un índice único
en la base; aquí se detecta antes para avisar bien. **Blando:** mismo día, total y NIF con otro número o sin número: solo un aviso.

`normalize_invoice_number` replica la columna generada `expenses.invoice_number_key` (el número sin ningún carácter que no sea `[0-9A-Za-z]`,
en mayúsculas; vacío es nulo). Una prueba del hito 2 la compara con la base.
"""

import re
from collections.abc import Sequence
from datetime import date

from cuadre.validators.types import ExistingExpense

_NOT_ALPHANUMERIC = re.compile(r"[^0-9A-Za-z]")


def normalize_invoice_number(raw: str | None) -> str | None:
    """`A-311`, `a 311` y `A311` son el mismo número. Se quita primero todo lo que no es ASCII alfanumérico y después se pasa a mayúsculas."""
    if raw is None:
        return None
    return _NOT_ALPHANUMERIC.sub("", raw).upper() or None


def is_hard_duplicate(tax_key: str | None, number_key: str | None, existing: Sequence[ExistingExpense]) -> bool:
    """Sin NIF o sin número (un ticket) no hay duplicado duro."""
    if tax_key is None or number_key is None:
        return False
    return any(e.supplier_tax_id == tax_key and e.invoice_number_key == number_key for e in existing)


def is_possible_duplicate(
    tax_key: str | None,
    number_key: str | None,
    expense_date: date | None,
    total_cents: int | None,
    existing: Sequence[ExistingExpense],
) -> bool:
    """Mismo día, total y NIF, **sin** el mismo número (si lo tuviera, sería duro)."""
    if tax_key is None or expense_date is None or total_cents is None:
        return False
    return any(
        e.supplier_tax_id == tax_key
        and e.expense_date == expense_date
        and e.total_cents == total_cents
        and not (number_key is not None and e.invoice_number_key == number_key)
        for e in existing
    )
