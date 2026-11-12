"""SQL de gastos (SQL explícito, sin ORM; ADR-0003). Toda escritura pasa por las funciones `app.*` del hito 2.

Las funciones reciben una conexión que ya tiene la identidad de la persona (`user_transaction`). Los errores de la base de datos se traducen
en `translate_db_error`; lo que no se reconoce se propaga y la API lo responde como un 500 sin detalles. Aquí también se decide qué NO se
traduce a propósito: `invalid_expense` con un campo que la API habría validado antes, y las CHECK (`23514`) y las categorías fuera de la
lista (`22P02`): si llegan es un fallo nuestro, no un error de la persona.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError
from cuadre.documents import errors as document_errors
from cuadre.documents import repository as documents
from cuadre.expenses import errors
from cuadre.validators import ExistingExpense, RegistrableValues

COLUMNS = (
    "id, origin::text AS origin, document_id, expense_date, supplier_name, supplier_tax_id, invoice_number, doc_type, "
    "supplier_scope::text AS supplier_scope, category::text AS category, base_cents, vat_cents, withholding_cents, total_cents, "
    "tax_breakdown, deductible_vat, suspicion_acknowledged, created_at, voided_at"
)

# El único campo de `invalid_expense` que la API deja pasar a la base es uno de estos (los de `create_manual_expense`).
FIELDS = frozenset(errors.FIELD_MESSAGES)

_PROBLEMS = {
    "expense_not_found": errors.expense_not_found,
    "expense_wrong_state": errors.expense_wrong_state,
    "suspicion_not_acknowledged": errors.suspicion_not_acknowledged,
}
_INDEXES = {
    "expenses_duplicate_invoice": errors.duplicate_expense,
    # Solo se da en una carrera (dos confirmaciones del mismo documento): la perdedora ve el documento ya registrado.
    "expenses_one_active_per_document": document_errors.document_wrong_state,
}


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` (hitos 1 y 2) -> problem+json. `None` si no es uno de ellos."""
    if exc.sqlstate == "23505":
        factory = _INDEXES.get(exc.diag.constraint_name or "")
        return factory() if factory is not None else None
    if exc.sqlstate == "P0001":
        message = exc.diag.message_primary or ""
        if message == "invalid_expense":
            field = exc.diag.message_detail or ""
            return errors.invalid_expense(field) if field in FIELDS else None
        if message in _PROBLEMS:
            return _PROBLEMS[message]()
    return documents.translate_db_error(exc)  # 42501, document_not_found, document_wrong_state, too_many_processing


# --- Lectura -----------------------------------------------------------------------------------------------------------------


def get(conn: Connection[DictRow], expense_id: UUID) -> DictRow | None:
    """El gasto de quien llama (también uno anulado), o `None`. `owner_id` se filtra además de la RLS."""
    return conn.execute(
        f"SELECT {COLUMNS} FROM public.expenses WHERE id = %(id)s AND owner_id = (SELECT private.read_owner())",  # noqa: S608
        {"id": expense_id},
    ).fetchone()


def list_page(
    conn: Connection[DictRow],
    *,
    limit: int,
    after: tuple[date, datetime, UUID] | None,
    year: int | None,
    month: int | None,
    category: str | None,
    include_voided: bool = False,
) -> list[DictRow]:
    """Una página de gastos vivos, del más reciente al más antiguo, en el orden del índice `expenses_by_owner_date`. `include_voided` (solo el gestor, que ve
    los anulados rotulados) añade también los anulados; con el valor por defecto la consulta es la de siempre."""
    where = ["owner_id = (SELECT private.read_owner())"]
    if not include_voided:
        where.append("voided_at IS NULL")
    params: dict[str, Any] = {"limit": limit}
    if year is not None:
        first = date(year, month or 1, 1)
        last = date(year + (month or 12) // 12, (month or 12) % 12 + 1, 1)
        where.append("expense_date >= %(first)s AND expense_date < %(last)s")
        params.update(first=first, last=last)
    if category is not None:
        where.append("category = %(category)s::public.expense_category")
        params["category"] = category
    if after is not None:
        where.append("(expense_date, created_at, id) < (%(d)s, %(c)s, %(i)s)")
        params.update(d=after[0], c=after[1], i=after[2])
    return conn.execute(
        f"SELECT {COLUMNS} FROM public.expenses WHERE {' AND '.join(where)} "  # noqa: S608
        "ORDER BY expense_date DESC, created_at DESC, id DESC LIMIT %(limit)s",
        params,
    ).fetchall()


def profile_tax_id(conn: Connection[DictRow]) -> str | None:
    """El NIF del perfil de quien llama (SPEC-W-005 lo rellena), tal cual: lo normalizan los validadores."""
    row = conn.execute("SELECT tax_id FROM public.business_profiles WHERE owner_id = (SELECT auth.uid())").fetchone()
    return None if row is None else row["tax_id"]


def existing_for_supplier(conn: Connection[DictRow], tax_key: str) -> tuple[ExistingExpense, ...]:
    """Los gastos VIVOS de quien llama con ese NIF de proveedor normalizado: lo que necesitan los avisos y el duplicado duro."""
    rows = conn.execute(
        "SELECT supplier_tax_id, invoice_number_key, expense_date, total_cents FROM public.expenses "
        "WHERE owner_id = (SELECT auth.uid()) AND voided_at IS NULL AND supplier_tax_id = %s",
        (tax_key,),
    ).fetchall()
    return tuple(
        ExistingExpense(
            supplier_tax_id=r["supplier_tax_id"],
            invoice_number_key=r["invoice_number_key"],
            expense_date=r["expense_date"],
            total_cents=r["total_cents"],
        )
        for r in rows
    )


def active_expense_id(conn: Connection[DictRow], document_id: UUID) -> UUID | None:
    row = conn.execute(
        "SELECT id FROM public.expenses WHERE document_id = %s AND voided_at IS NULL AND owner_id = (SELECT auth.uid())",
        (document_id,),
    ).fetchone()
    return None if row is None else row["id"]


# --- Escritura (solo funciones app.*) ------------------------------------------------------------------------------------------


def lock_document(conn: Connection[DictRow], document_id: UUID) -> DictRow:
    """El documento de quien llama, bloqueado hasta el fin de la transacción (`document_not_found` si no existe o está descartado)."""
    row = conn.execute("SELECT * FROM app.lock_document(%s)", (document_id,)).fetchone()
    assert row is not None
    return row


def database_values(values: RegistrableValues) -> dict[str, Any]:
    """`RegistrableValues` -> el `p_values` de `app.register_expense_from_document` (las mismas claves; la base genera la clave del número)."""
    return {
        "expense_date": values.expense_date.isoformat(),
        "supplier_name": values.supplier_name,
        "supplier_tax_id": values.supplier_tax_id,
        "supplier_scope": values.supplier_scope,
        "invoice_number": values.invoice_number,
        "doc_type": values.doc_type,
        "base_cents": values.base_cents,
        "vat_cents": values.vat_cents,
        "withholding_cents": values.withholding_cents,
        "total_cents": values.total_cents,
        "tax_breakdown": [
            {"vat_rate": line.vat_rate, "base_cents": line.base_cents, "vat_cents": line.vat_cents}
            for line in values.tax_lines
        ],
        "deductible_vat": values.deductible_vat,
    }


def register(
    conn: Connection[DictRow], document_id: UUID, category: str, values: RegistrableValues, acknowledged: bool
) -> UUID:
    row = conn.execute(
        "SELECT app.register_expense_from_document(%s, %s::public.expense_category, %s, %s) AS id",
        (document_id, category, Jsonb(database_values(values)), acknowledged),
    ).fetchone()
    assert row is not None
    return row["id"]


def create_manual(conn: Connection[DictRow], day: date, concept: str, category: str, amount_cents: int) -> UUID:
    row = conn.execute(
        "SELECT app.create_manual_expense(%s, %s, %s::public.expense_category, %s) AS id",
        (day, concept, category, amount_cents),
    ).fetchone()
    assert row is not None
    return row["id"]


def set_category(conn: Connection[DictRow], expense_id: UUID, category: str) -> None:
    conn.execute("SELECT app.set_expense_category(%s, %s::public.expense_category)", (expense_id, category))


def void(conn: Connection[DictRow], expense_id: UUID) -> str | None:
    """Anula el gasto y devuelve el estado al que vuelve su documento (`review` o `extraction_failed`), o `None` si era manual."""
    row = conn.execute("SELECT app.void_expense(%s)::text AS status", (expense_id,)).fetchone()
    assert row is not None
    return row["status"]
