"""Ayudas de las pruebas de `expenses`: una fila válida (de documento o manual) y su inserción directa como dueño de la base de datos."""

from datetime import date
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from tests.support import Doc, Person

INSERT = """
insert into public.expenses (owner_id, origin, document_id, expense_date, supplier_name, supplier_tax_id, invoice_number, doc_type,
                             supplier_scope, category, base_cents, vat_cents, withholding_cents, total_cents, tax_breakdown,
                             deductible_vat, voided_at)
values (%(owner)s, %(origin)s, %(document)s, %(date)s, %(name)s, %(tax_id)s, %(number)s, %(doc_type)s, %(scope)s, %(category)s,
        %(base)s, %(vat)s, %(withholding)s, %(total)s, %(lines)s, %(deductible)s, %(voided)s)
returning id
"""

LINE = {"vat_rate": "21", "base_cents": 10000, "vat_cents": 2100}
ZERO_LINE = {"vat_rate": "0", "base_cents": 10000, "vat_cents": 0}


def params(owner: Person, doc: Doc | None, **overrides: Any) -> dict[str, Any]:
    """Un gasto de documento válido (12.100 céntimos: base 10.000 + 21 % de IVA) con lo que se quiera cambiar."""
    base: dict[str, Any] = {
        "owner": owner.id,
        "origin": "document",
        "document": doc.id if doc else None,
        "date": date(2026, 10, 15),
        "name": "Proveedor Sintético SL",
        "tax_id": "B00000042",
        "number": "A-311",
        "doc_type": "full_invoice",
        "scope": "national",
        "category": "software",
        "base": 10000,
        "vat": 2100,
        "withholding": 0,
        "total": 12100,
        "lines": [LINE],
        "deductible": True,
        "voided": None,
    }
    merged = {**base, **overrides}
    merged["lines"] = Jsonb(merged["lines"])
    return merged


def manual(owner: Person, **overrides: Any) -> dict[str, Any]:
    """Un gasto sin factura válido (294,00 €)."""
    base: dict[str, Any] = {
        "origin": "manual",
        "name": "Cuota de autónomos",
        "tax_id": None,
        "number": None,
        "doc_type": None,
        "scope": None,
        "category": "self_employed_fee",
        "base": 29400,
        "vat": 0,
        "total": 29400,
        "lines": [],
        "deductible": False,
    }
    return params(owner, None, **{**base, **overrides})


def insert(admin: Connection[DictRow], values: dict[str, Any]) -> Any:
    row = admin.execute(INSERT, values).fetchone()
    assert row is not None
    return row["id"]
