"""SQL de lectura de los borradores trimestrales (SQL explícito, sin ORM; ADR-0003). Solo lee: ninguna función `app.*`, ninguna escritura.

Las funciones reciben una conexión que ya tiene la identidad de la persona (`user_transaction`) y filtran `owner_id = (SELECT auth.uid())` además
de la RLS, como el resto de lecturas. Reciben un rango `[start, end)` de fechas y no un trimestre: el 130 (SPEC-W-009) las reutiliza con un rango
desde enero. Cada consulta corta en `QUARTER_MAX_DOCUMENTS + 1` filas para acotar la memoria; el dominio es quien decide `QuarterTooLarge`.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.invoicing.numbering import display_number
from cuadre.tax import ExpenseLine, ExpenseRow, InvoiceRow, UnsupportedVatRate
from cuadre.tax.limits import QUARTER_MAX_DOCUMENTS
from cuadre.validators.vat import parse_rate

DEFAULT_LIMIT = QUARTER_MAX_DOCUMENTS + 1

INVOICES_SQL = """
SELECT id, series_code, number, issue_date, tax_treatment::text AS tax_treatment, vat_rate, base_cents, vat_cents
  FROM public.invoices
 WHERE owner_id = (SELECT auth.uid()) AND issue_date >= %(start)s AND issue_date < %(end)s
 ORDER BY issue_date, id
 LIMIT %(limit)s
"""

EXPENSES_SQL = """
SELECT id, supplier_name, expense_date, deductible_vat, tax_breakdown
  FROM public.expenses
 WHERE owner_id = (SELECT auth.uid()) AND voided_at IS NULL AND expense_date >= %(start)s AND expense_date < %(end)s
 ORDER BY expense_date, id
 LIMIT %(limit)s
"""


def invoice_rows(conn: Connection[DictRow], start: date, end: date, *, limit: int = DEFAULT_LIMIT) -> list[InvoiceRow]:
    """Las facturas (también las rectificativas, con su diferencia y su signo) expedidas en `[start, end)`. El `label` es el número que se enseña."""
    rows = conn.execute(INVOICES_SQL, {"start": start, "end": end, "limit": limit}).fetchall()
    return [
        InvoiceRow(
            id=str(row["id"]),
            label=display_number(row["series_code"], row["number"]),
            issue_date=row["issue_date"],
            tax_treatment=row["tax_treatment"],
            vat_rate=Decimal(row["vat_rate"]),
            base_cents=row["base_cents"],
            vat_cents=row["vat_cents"],
        )
        for row in rows
    ]


def _lines(breakdown: Any) -> tuple[ExpenseLine, ...]:
    lines = []
    for line in breakdown:
        rate = parse_rate(line.get("vat_rate")) if isinstance(line, dict) else None
        if rate is None:
            # Un dato corrupto no se esconde ni se suma como cero; el mensaje no repite lo que había.
            raise UnsupportedVatRate("Un gasto trae una línea con un tipo de IVA que no se puede leer.")
        lines.append(ExpenseLine(rate, line["base_cents"], line["vat_cents"]))
    return tuple(lines)


def expense_rows(conn: Connection[DictRow], start: date, end: date, *, limit: int = DEFAULT_LIMIT) -> list[ExpenseRow]:
    """Los gastos vivos (no anulados) con fecha en `[start, end)`. El `label` es el proveedor; los manuales llegan sin líneas y sin IVA deducible."""
    rows = conn.execute(EXPENSES_SQL, {"start": start, "end": end, "limit": limit}).fetchall()
    return [
        ExpenseRow(
            id=str(row["id"]),
            label=row["supplier_name"],
            expense_date=row["expense_date"],
            deductible_vat=row["deductible_vat"],
            voided=False,
            lines=_lines(row["tax_breakdown"]),
        )
        for row in rows
    ]
