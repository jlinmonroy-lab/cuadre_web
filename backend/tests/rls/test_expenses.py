"""AC-15, AC-16 · la tabla `expenses`: quién la ve, quién la escribe y qué no admite venga de donde venga (SPEC-W-003 §5.2).

Las funciones `app.*` y las transiciones de `documents` están en `test_expenses_states.py`; aquí se prueba la tabla como la red de
seguridad que es: varias comprobaciones escriben directamente como dueño de la base de datos para demostrar que ni una CHECK, ni un
índice, ni el trigger dependen de que la API se porte bien.
"""

import json
import re
from datetime import UTC, date, datetime
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.rls.expenses_support import INSERT, LINE, ZERO_LINE, insert, manual, params
from tests.support import Cast, Doc, Person, Pool, advance, apply_scenario, attempt, call, new_document, visible_owners


def violated(admin: Connection[DictRow], values: dict[str, Any], error: type[psycopg.Error]) -> str | None:
    with pytest.raises(error) as info:
        admin.execute(INSERT, values)
    return info.value.diag.constraint_name


def count(admin: Connection[DictRow], owner: Person) -> int:
    found = admin.execute("select count(*) as n from public.expenses where owner_id = %s", (owner.id,)).fetchone()
    assert found is not None
    return int(found["n"])


@pytest.fixture
def doc(app_pool: Pool, cast: Cast) -> Doc:
    return new_document(app_pool, cast.alicia)


# --- la tabla rechaza lo mal formado -------------------------------------------------------------------------------------------


def test_valid_rows_insert_so_the_rejections_prove_something(admin: Connection[DictRow], cast: Cast, doc: Doc) -> None:
    insert(admin, params(cast.alicia, doc))
    insert(admin, manual(cast.alicia))
    assert count(admin, cast.alicia) == 2
    row = admin.execute(
        "select invoice_number_key, tax_breakdown from public.expenses where owner_id = %s and origin = 'document'",
        (cast.alicia.id,),
    ).fetchone()
    assert row is not None and row["invoice_number_key"] == "A311" and row["tax_breakdown"] == [LINE]


ELEVEN = [{"vat_rate": "21", "base_cents": 1000, "vat_cents": 210}] * 11
TEN = [{"vat_rate": "21", "base_cents": 1000, "vat_cents": 210}] * 10

VALID_DOCUMENT_VARIANTS: list[dict[str, Any]] = [
    {"total": 12101},  # ±1 céntimo de tolerancia (D-03)
    {"total": 12099},
    {"withholding": 1500, "total": 10600},
    {"scope": "eu", "deductible": False},
    {"doc_type": "ticket", "number": None},
    {"doc_type": "simplified_invoice", "deductible": False},
    {"doc_type": "receipt", "deductible": False},
    {"lines": TEN, "base": 10000, "vat": 2100},
    {
        "base": 999999999999999,
        "vat": 0,
        "total": 999999999999999,
        "deductible": False,
        "lines": [{"vat_rate": "0", "base_cents": 999999999999999, "vat_cents": 0}],
    },
    {"base": 10000, "vat": 0, "total": 10000, "lines": [ZERO_LINE], "deductible": False},  # IVA 0 %: no deducible
    {"date": date(2000, 1, 1)},
    {"tax_id": "A" * 20},
    {"tax_id": "RO957", "number": "x" * 64},
]


@pytest.mark.parametrize("variant", VALID_DOCUMENT_VARIANTS, ids=lambda v: ",".join(sorted(v)))
def test_valid_variants_of_a_document_expense_are_accepted(
    admin: Connection[DictRow], cast: Cast, doc: Doc, variant: dict[str, Any]
) -> None:
    # Anulados al insertar: así no choca ninguno con el índice de «un gasto vivo por documento».
    insert(admin, params(cast.alicia, doc, voided=datetime.now(UTC), **variant))


CHECK_CASES: list[tuple[str, dict[str, Any]]] = [
    # importes: enteros, sin signo, de 15 cifras como mucho, y el total mayor que cero
    ("expenses_amounts_range", {"withholding": -1}),
    (
        "expenses_amounts_range",
        {"vat": -1, "total": 9999, "lines": [{"vat_rate": "21", "base_cents": 10000, "vat_cents": -1}]},
    ),
    (
        "expenses_amounts_range",
        {
            "base": 10**15,
            "vat": 0,
            "total": 10**15,
            "deductible": False,
            "lines": [{"vat_rate": "0", "base_cents": 10**15, "vat_cents": 0}],
        },
    ),
    ("expenses_amounts_range", {"withholding": 10**15}),
    # total coherente con base + IVA − retención (±1 céntimo)
    ("expenses_total_coherent", {"total": 12102}),
    ("expenses_total_coherent", {"total": 12098}),
    ("expenses_total_coherent", {"total": 12100, "withholding": 1500}),
    # deducible solo de un proveedor nacional con cuota
    ("expenses_deductible_rule", {"scope": "eu", "deductible": True}),
    ("expenses_deductible_rule", {"base": 10000, "vat": 0, "total": 10000, "lines": [ZERO_LINE], "deductible": True}),
    # un gasto de documento: proveedor identificado, tipo y líneas que suman exactamente
    ("expenses_document_shape", {"tax_id": None}),
    ("expenses_document_shape", {"scope": None}),
    ("expenses_document_shape", {"doc_type": None}),
    ("expenses_document_shape", {"lines": [{"vat_rate": "21", "base_cents": 9999, "vat_cents": 2100}]}),
    ("expenses_document_shape", {"lines": [{"vat_rate": "21", "base_cents": 10000, "vat_cents": 2101}]}),
    ("expenses_document_shape", {"lines": [{"vat_rate": "21", "base_cents": 10000.5, "vat_cents": 2100}]}),
    ("expenses_document_shape", {"lines": [{"vat_rate": "21", "base_cents": "10000", "vat_cents": "2100"}]}),
    ("expenses_document_shape", {"lines": [{"base_cents": 10000, "vat_cents": 2100}]}),
    ("expenses_document_shape", {"lines": [{"vat_rate": 21, "base_cents": 10000, "vat_cents": 2100}]}),
    ("expenses_document_shape", {"lines": [{"vat_rate": "21", "base_cents": -10000, "vat_cents": 2100}]}),
    ("expenses_document_shape", {"lines": []}),
    ("expenses_document_shape", {"lines": {"vat_rate": "21", "base_cents": 10000, "vat_cents": 2100}}),
    ("expenses_document_shape", {"lines": [1]}),
    # una línea mal formada no se esconde detrás de otras que suman bien
    ("expenses_document_shape", {"lines": [LINE, {"vat_rate": "0", "base_cents": 5.5, "vat_cents": 0}]}),
    ("expenses_document_shape", {"lines": [LINE, {"vat_rate": "0", "base_cents": "0", "vat_cents": 0}]}),
    ("expenses_document_shape", {"lines": [LINE, {"vat_rate": "0", "base_cents": None, "vat_cents": 0}]}),
    ("expenses_document_shape", {"lines": [LINE, {"vat_rate": "0", "base_cents": 0, "vat_cents": 5.5}]}),
    ("expenses_document_shape", {"lines": [LINE, {"vat_rate": "0", "base_cents": 0, "vat_cents": "0"}]}),
    ("expenses_document_shape", {"lines": [LINE, {"vat_rate": "0", "base_cents": 0, "vat_cents": None}]}),
    ("expenses_document_shape", {"lines": ELEVEN, "base": 11000, "vat": 2310, "total": 13310}),
    # uno manual no lleva nada de eso
    ("expenses_manual_shape", {"tax_id": "B00000042"}),
    ("expenses_manual_shape", {"number": "A-1"}),
    ("expenses_manual_shape", {"scope": "national"}),
    ("expenses_manual_shape", {"doc_type": "ticket"}),
    ("expenses_manual_shape", {"vat": 100, "total": 29500}),
    ("expenses_manual_shape", {"withholding": 100, "total": 29300}),
    ("expenses_manual_shape", {"total": 29401}),
    ("expenses_manual_shape", {"lines": [LINE]}),
    # texto
    ("expenses_supplier_name_length", {"name": ""}),
    ("expenses_supplier_name_length", {"name": "x" * 201}),
    ("expenses_invoice_number_length", {"number": ""}),
    ("expenses_invoice_number_length", {"number": "x" * 65}),
    ("expenses_doc_type_known", {"doc_type": "other"}),
    ("expenses_doc_type_known", {"doc_type": "not_an_invoice"}),
    ("expenses_doc_type_known", {"doc_type": ""}),
    ("expenses_date_not_ancient", {"date": date(1999, 12, 31)}),
]

TAX_ID_CASES = [
    "b00000042",
    "B000",
    "B" * 21,
    "B000-00042",
    "B00000042" + chr(10),
    chr(10) + "B00000042",
    " B00000042",
    "B0000004Ñ",
    "B 0000042",
    "",
]


MANUAL_CONSTRAINTS = {"expenses_manual_shape", "expenses_supplier_name_length"}


@pytest.mark.parametrize(
    ("constraint", "change"), CHECK_CASES, ids=lambda c: c if isinstance(c, str) else ",".join(sorted(c))
)
def test_the_table_rejects_malformed_rows(
    admin: Connection[DictRow], cast: Cast, doc: Doc, constraint: str, change: dict[str, Any]
) -> None:
    """AC-16 · cada CHECK salta por lo suyo (el nombre de la restricción lo demuestra) y no entra ninguna fila."""
    values = manual(cast.alicia, **change) if constraint in MANUAL_CONSTRAINTS else params(cast.alicia, doc, **change)
    assert violated(admin, values, psycopg.errors.CheckViolation) == constraint
    assert count(admin, cast.alicia) == 0


def test_a_manual_expense_is_never_deductible(admin: Connection[DictRow], cast: Cast) -> None:
    """Sin proveedor nacional no hay IVA que deducir: salta `deductible_rule` y, si esa faltara, `manual_shape`."""
    assert violated(admin, manual(cast.alicia, deductible=True), psycopg.errors.CheckViolation) in (
        "expenses_deductible_rule",
        "expenses_manual_shape",
    )


@pytest.mark.parametrize("tax_id", TAX_ID_CASES)
def test_the_supplier_tax_id_must_be_a_compact_key_even_with_a_line_break(
    admin: Connection[DictRow], cast: Cast, doc: Doc, tax_id: str
) -> None:
    """La rendija del `$` (B.1): una clave que acaba en salto de línea no pasa la CHECK de la base."""
    assert (
        violated(admin, params(cast.alicia, doc, tax_id=tax_id), psycopg.errors.CheckViolation)
        == "expenses_tax_id_form"
    )


def test_origin_and_document_go_together(admin: Connection[DictRow], cast: Cast, doc: Doc) -> None:
    assert (
        violated(admin, params(cast.alicia, None), psycopg.errors.CheckViolation) == "expenses_origin_matches_document"
    )
    assert (
        violated(admin, manual(cast.alicia, document=doc.id), psycopg.errors.CheckViolation)
        == "expenses_origin_matches_document"
    )
    assert count(admin, cast.alicia) == 0


def test_required_columns_and_enums(admin: Connection[DictRow], cast: Cast, doc: Doc) -> None:
    with pytest.raises(psycopg.errors.NotNullViolation):
        admin.execute(INSERT, params(cast.alicia, doc, category=None))
    for change in ({"category": "inventada"}, {"origin": "otro"}, {"scope": "world"}):
        with pytest.raises(psycopg.errors.InvalidTextRepresentation):
            admin.execute(INSERT, params(cast.alicia, doc, **change))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin.execute(
            INSERT, params(cast.alicia, None, origin="document", document="00000000-0000-4000-8000-000000000000")
        )
    assert count(admin, cast.alicia) == 0


# --- índices: un gasto vivo por documento y por factura --------------------------------------------------------------------------


def test_the_same_supplier_and_invoice_number_cannot_be_alive_twice(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    """AC-08 · el número se compara normalizado (`A-311`, `a311`, `A 311` son el mismo)."""
    first = new_document(app_pool, cast.alicia)
    insert(admin, params(cast.alicia, first, number="A-311"))
    for number in ("a311", "A 311", " a-311 ", "A.311", "A_311", "a/311"):
        other = new_document(app_pool, cast.alicia)
        assert (
            violated(admin, params(cast.alicia, other, number=number), psycopg.errors.UniqueViolation)
            == "expenses_duplicate_invoice"
        )
    assert count(admin, cast.alicia) == 1


def test_a_different_supplier_number_or_person_is_not_a_duplicate(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    insert(admin, params(cast.alicia, new_document(app_pool, cast.alicia), number="A-311"))
    insert(admin, params(cast.alicia, new_document(app_pool, cast.alicia), number="A-312"))
    insert(admin, params(cast.alicia, new_document(app_pool, cast.alicia), tax_id="B00000075", number="A-311"))
    insert(admin, params(cast.beto, new_document(app_pool, cast.beto), number="A-311"))
    for _ in range(2):  # un ticket no tiene número: no hay duplicado duro
        insert(admin, params(cast.alicia, new_document(app_pool, cast.alicia), doc_type="ticket", number=None))
    assert count(admin, cast.alicia) == 5


def test_a_voided_expense_no_longer_blocks_the_same_invoice(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    first = insert(admin, params(cast.alicia, new_document(app_pool, cast.alicia), number="A-311"))
    second = new_document(app_pool, cast.alicia)
    assert violated(admin, params(cast.alicia, second, number="a311"), psycopg.errors.UniqueViolation)
    admin.execute("update public.expenses set voided_at = now() where id = %s", (first,))
    insert(admin, params(cast.alicia, second, number="a311"))


def test_a_number_without_any_letter_or_digit_has_no_key_and_does_not_count_as_a_duplicate(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    """Límite conocido (B.3): `---` normaliza a nada, y sin clave el índice no compara. Lo cubre `required_data`/el aviso blando."""
    for _ in range(2):
        insert(admin, params(cast.alicia, new_document(app_pool, cast.alicia), number="---"))
    key = admin.execute(
        "select invoice_number_key from public.expenses where owner_id = %s limit 1", (cast.alicia.id,)
    ).fetchone()
    assert key == {"invoice_number_key": None}


def test_a_document_has_at_most_one_alive_expense(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast, doc: Doc
) -> None:
    first = insert(admin, params(cast.alicia, doc, number="A-1"))
    assert (
        violated(admin, params(cast.alicia, doc, number="A-2"), psycopg.errors.UniqueViolation)
        == "expenses_one_active_per_document"
    )
    admin.execute("update public.expenses set voided_at = now() where id = %s", (first,))
    insert(admin, params(cast.alicia, doc, number="A-2"))  # anulado el primero, cabe otro: es un gasto nuevo


# --- el trigger: solo cambian la categoría y voided_at ---------------------------------------------------------------------------

IMMUTABLE = [
    "id = gen_random_uuid()",
    "owner_id = gen_random_uuid()",
    "origin = 'manual'",
    "document_id = null",
    "expense_date = date '2026-10-16'",
    "supplier_name = 'otro'",
    "supplier_tax_id = 'B00000075'",
    "invoice_number = 'A-312'",
    "doc_type = 'ticket'",
    "supplier_scope = 'eu'",
    "base_cents = base_cents + 1",
    "vat_cents = vat_cents + 1",
    "withholding_cents = 1",
    "total_cents = total_cents + 1",
    "tax_breakdown = '[]'",
    "deductible_vat = false",
    "suspicion_acknowledged = true",
    "created_at = now() - interval '1 day'",
]


def stored(admin: Connection[DictRow], expense_id: Any) -> dict[str, Any]:
    found = admin.execute("select * from public.expenses where id = %s", (expense_id,)).fetchone()
    assert found is not None
    return found


@pytest.mark.parametrize("assignment", IMMUTABLE)
def test_every_column_but_category_and_voided_at_is_frozen(
    admin: Connection[DictRow], cast: Cast, doc: Doc, assignment: str
) -> None:
    expense_id = insert(admin, params(cast.alicia, doc))
    before = stored(admin, expense_id)
    with pytest.raises(psycopg.errors.RaiseException, match="expense_immutable_column"):
        admin.execute(f"update public.expenses set {assignment} where id = %s", (expense_id,))  # noqa: S608
    assert stored(admin, expense_id) == before


def test_the_generated_key_cannot_be_written(admin: Connection[DictRow], cast: Cast, doc: Doc) -> None:
    expense_id = insert(admin, params(cast.alicia, doc))
    with pytest.raises(psycopg.errors.GeneratedAlways):
        admin.execute("update public.expenses set invoice_number_key = 'X' where id = %s", (expense_id,))


def test_category_changes_and_updated_at_follows_unless_set_on_purpose(
    admin: Connection[DictRow], cast: Cast, doc: Doc
) -> None:
    expense_id = insert(admin, params(cast.alicia, doc))
    first = stored(admin, expense_id)["updated_at"]
    admin.execute("update public.expenses set category = 'training' where id = %s", (expense_id,))
    changed = stored(admin, expense_id)
    assert changed["category"] == "training" and changed["updated_at"] > first
    admin.execute("update public.expenses set updated_at = now() - interval '10 minutes' where id = %s", (expense_id,))
    assert stored(admin, expense_id)["updated_at"] < changed["updated_at"]


def test_a_voided_expense_stays_voided_and_keeps_its_category(admin: Connection[DictRow], cast: Cast, doc: Doc) -> None:
    expense_id = insert(admin, params(cast.alicia, doc))
    admin.execute("update public.expenses set voided_at = now() where id = %s", (expense_id,))
    voided = stored(admin, expense_id)
    assert voided["voided_at"] is not None
    for statement in (
        "update public.expenses set voided_at = null where id = %s",
        "update public.expenses set voided_at = now() + interval '1 hour' where id = %s",
        "update public.expenses set category = 'training' where id = %s",
        "update public.expenses set voided_at = null, category = 'training' where id = %s",
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="expense_already_voided"):
            admin.execute(statement, (expense_id,))
    assert stored(admin, expense_id) == voided


# --- quién la ve y quién la escribe (AC-15) --------------------------------------------------------------------------------------


def manual_by_function(pool: Pool, person: Person, concept: str = "Cuota de autónomos") -> Any:
    out = call(pool, person, "create_manual_expense", date(2026, 10, 1), concept, "self_employed_fee", 29400)
    assert not out.error, out.message
    return out.rows[0]["create_manual_expense"]


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_writes_the_table_directly_not_even_its_owner(app_pool: Pool, cast: Cast, who: str) -> None:
    mine = manual_by_function(app_pool, cast.alicia)
    actor = cast[who]
    insert_sql = INSERT.replace("returning id", "")
    inserted = attempt(app_pool, actor, insert_sql, manual(actor))
    updated = attempt(app_pool, actor, "update public.expenses set category = 'other' where id = %s", (mine,))
    deleted = attempt(app_pool, actor, "delete from public.expenses where id = %s", (mine,))
    truncated = attempt(app_pool, actor, "truncate public.expenses")
    for name, out in (("insert", inserted), ("update", updated), ("delete", deleted), ("truncate", truncated)):
        assert out.sqlstate == "42501", f"{who}: {name} -> {out.sqlstate} {out.message}"


def test_the_owner_sees_her_voided_expenses_and_only_hers(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    mine, theirs = manual_by_function(app_pool, cast.alicia), manual_by_function(app_pool, cast.beto)
    assert not call(app_pool, cast.alicia, "void_expense", mine).error
    seen = attempt(app_pool, cast.alicia, "select id, voided_at from public.expenses")
    assert [r["id"] for r in seen.rows] == [mine] and seen.rows[0]["voided_at"] is not None
    assert [r["id"] for r in attempt(app_pool, cast.beto, "select id from public.expenses").rows] == [theirs]


@pytest.mark.parametrize("scenario", ["baseline", "pending", "revoked", "declined"])
def test_a_gestor_without_an_active_link_sees_nothing(app_pool: Pool, cast: Cast, scenario: str) -> None:
    manual_by_function(app_pool, cast.alicia)
    apply_scenario(app_pool, cast, scenario)
    assert visible_owners(app_pool, cast.gina, "expenses", "owner_id") == set()
    assert visible_owners(app_pool, cast.gus, "expenses", "owner_id") == set()


def test_an_active_gestor_reads_including_voided_and_revoking_cuts_access_at_once(app_pool: Pool, cast: Cast) -> None:
    alive, voided = manual_by_function(app_pool, cast.alicia), manual_by_function(app_pool, cast.alicia, "Otro")
    assert not call(app_pool, cast.alicia, "void_expense", voided).error
    link = apply_scenario(app_pool, cast, "active")
    seen = attempt(app_pool, cast.gina, "select id from public.expenses order by id")
    assert {r["id"] for r in seen.rows} == {alive, voided}
    assert visible_owners(app_pool, cast.gus, "expenses", "owner_id") == set(), "un gestor sin vínculo no ve nada"

    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert attempt(app_pool, cast.gina, "select id from public.expenses").rows == []


def test_the_admin_sees_no_expense_even_with_an_active_link_around(app_pool: Pool, cast: Cast) -> None:
    manual_by_function(app_pool, cast.alicia)
    manual_by_function(app_pool, cast.beto)
    apply_scenario(app_pool, cast, "active")
    assert attempt(app_pool, cast.adan, "select id from public.expenses").rows == []


def test_records_are_removed_with_the_account_but_the_log_stays(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """La FK en cascada deja la puerta abierta a CONF-004 (retención); el registro de actividad no tiene claves foráneas."""
    advance_registered(app_pool, cast)
    manual_by_function(app_pool, cast.alicia)
    logged = admin.execute(
        "select count(*) as n from public.activity_log where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert count(admin, cast.alicia) == 2

    admin.execute("delete from auth.users where id = %s", (cast.alicia.id,))
    assert count(admin, cast.alicia) == 0
    assert admin.execute("select 1 from public.documents where owner_id = %s", (cast.alicia.id,)).fetchone() is None
    assert (
        admin.execute("select count(*) as n from public.activity_log where owner_id = %s", (cast.alicia.id,)).fetchone()
        == logged
    )


def advance_registered(pool: Pool, cast: Cast) -> Doc:
    return advance(pool, cast.alicia, new_document(pool, cast.alicia), "registered")


def test_the_activity_log_keeps_no_financial_data(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """T3-08 · una última comprobación sobre todo lo que dejan las funciones de gastos."""
    manual_by_function(app_pool, cast.alicia, "Concepto secreto 29400")
    advance_registered(app_pool, cast)
    entries = admin.execute(
        "select action, metadata from public.activity_log where owner_id = %s and action like 'expense.%%'",
        (cast.alicia.id,),
    ).fetchall()
    assert len(entries) == 2
    text = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "",
        json.dumps([e["metadata"] for e in entries]),
    )
    for secret in ("secreto", "29400", "12100", "10000", "2100", "B00000042", "Proveedor", "A-311", "R-"):
        assert secret not in text, f"el registro de actividad contiene «{secret}»"
