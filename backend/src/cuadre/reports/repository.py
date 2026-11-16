"""Lectura de los gastos del reporte mensual (SPEC-W-013 §5.2). Solo lee, con la identidad de la persona y su RLS: `owner_id = (SELECT private.read_owner())`.

Pide una fila más del tope de documentos del cierre: así el dominio ve que se pasa y falla (`ReportTooLarge`) en vez de cortar los datos en silencio.
"""

from datetime import date

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.closing.limits import CLOSING_MAX_DOCUMENTS
from cuadre.reports.types import CategorisedExpense

LIMIT = CLOSING_MAX_DOCUMENTS + 1

EXPENSES_SQL = """
SELECT id, category::text AS category, base_cents, vat_cents, deductible_vat
  FROM public.expenses
 WHERE owner_id = (SELECT private.read_owner()) AND voided_at IS NULL AND expense_date >= %(start)s AND expense_date < %(end)s
 ORDER BY expense_date, id
 LIMIT %(limit)s
"""


def expenses_with_category(conn: Connection[DictRow], start: date, end: date) -> list[CategorisedExpense]:
    """Los gastos vivos (no anulados) con fecha en `[start, end)` y su categoría; los manuales traen IVA 0."""
    rows = conn.execute(EXPENSES_SQL, {"start": start, "end": end, "limit": LIMIT}).fetchall()
    return [
        CategorisedExpense(
            id=str(row["id"]),
            category=row["category"],
            base_cents=row["base_cents"],
            vat_cents=row["vat_cents"],
            deductible_vat=row["deductible_vat"],
            voided=False,
        )
        for row in rows
    ]
