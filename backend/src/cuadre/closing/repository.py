"""Lecturas del cierre mensual (SPEC-W-012 §5.4). Solo leen, con la identidad de la persona y su RLS: `owner_id = (SELECT private.read_owner())`.

Cada consulta pide una fila más del tope de documentos del cierre: así el dominio ve que se pasa y falla (`ClosingTooLarge`) en vez de cortar los datos en silencio.
"""

from datetime import date

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.closing.limits import CLOSING_MAX_DOCUMENTS
from cuadre.closing.types import MonthExpense, MonthInvoice

LIMIT = CLOSING_MAX_DOCUMENTS + 1

INVOICES_SQL = """
SELECT id, issue_date, kind::text AS kind, base_cents, client_id, client_name, client_scope::text AS scope
  FROM public.invoices
 WHERE owner_id = (SELECT private.read_owner()) AND issue_date >= %(start)s AND issue_date < %(end)s
 ORDER BY issue_date, id
 LIMIT %(limit)s
"""

EXPENSES_SQL = """
SELECT id, expense_date, base_cents, vat_cents, deductible_vat
  FROM public.expenses
 WHERE owner_id = (SELECT private.read_owner()) AND voided_at IS NULL AND expense_date >= %(start)s AND expense_date < %(end)s
 ORDER BY expense_date, id
 LIMIT %(limit)s
"""

FIRST_DATES_SQL = """
SELECT (SELECT min(issue_date) FROM public.invoices WHERE owner_id = (SELECT private.read_owner())) AS first_invoice,
       (SELECT min(expense_date) FROM public.expenses WHERE owner_id = (SELECT private.read_owner()) AND voided_at IS NULL) AS first_expense
"""


def first_dates(conn: Connection[DictRow]) -> tuple[date | None, date | None]:
    """La fecha de la primera factura emitida y del primer gasto no anulado de la persona (o `None`): con el alta de la cuenta fijan su primer mes."""
    row = conn.execute(FIRST_DATES_SQL).fetchone()
    assert row is not None
    return row["first_invoice"], row["first_expense"]


def invoices_between(conn: Connection[DictRow], start: date, end: date) -> list[MonthInvoice]:
    """Las facturas (también las rectificativas, con su diferencia y su signo) expedidas en `[start, end)`."""
    rows = conn.execute(INVOICES_SQL, {"start": start, "end": end, "limit": LIMIT}).fetchall()
    return [
        MonthInvoice(
            id=str(row["id"]),
            issue_date=row["issue_date"],
            kind=row["kind"],
            base_cents=row["base_cents"],
            client_id=str(row["client_id"]),
            client_name=row["client_name"],
            scope=row["scope"],
        )
        for row in rows
    ]


def expenses_between(conn: Connection[DictRow], start: date, end: date) -> list[MonthExpense]:
    """Los gastos vivos (no anulados) con fecha en `[start, end)`; los manuales traen IVA 0."""
    rows = conn.execute(EXPENSES_SQL, {"start": start, "end": end, "limit": LIMIT}).fetchall()
    return [
        MonthExpense(
            id=str(row["id"]),
            expense_date=row["expense_date"],
            base_cents=row["base_cents"],
            vat_cents=row["vat_cents"],
            deductible_vat=row["deductible_vat"],
            voided=False,
        )
        for row in rows
    ]
