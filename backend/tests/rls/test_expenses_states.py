"""AC-02, AC-08, AC-09, AC-11, AC-12, AC-13, AC-16, AC-17 · las funciones `app.*` de gastos y el `documents_guard` ampliado (SPEC-W-003 §5.2).

Las rutas llegan en el hito 3; aquí se prueban las funciones como la red de seguridad que son: varias comprobaciones escriben
directamente como dueño de la base de datos para demostrar que `documents` no admite lo ilegal venga de donde venga.
"""

import json
import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.agents import normalize_extraction
from cuadre.db import user_transaction
from cuadre.validators import RegistrableValues, ValidationContext, from_stored, validate
from tests.agents.support import example_response
from tests.rls.expenses_support import INSERT, params
from tests.support import (
    GOOD_EXTRACTION,
    GOOD_VALUES,
    Cast,
    Doc,
    Pool,
    advance,
    attempt,
    call,
    new_document,
    register,
    values,
)

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LINES = [{"vat_rate": "21", "base_cents": 10000, "vat_cents": 2100}]


# --- ayudas -------------------------------------------------------------------------------------------------------------------


def doc_row(admin: Connection[DictRow], doc: Doc) -> dict[str, Any]:
    found = admin.execute("select * from public.documents where id = %s", (doc.id,)).fetchone()
    assert found is not None
    return found


def expense_row(admin: Connection[DictRow], expense_id: Any) -> dict[str, Any]:
    found = admin.execute("select * from public.expenses where id = %s", (expense_id,)).fetchone()
    assert found is not None
    return found


def expenses_of(admin: Connection[DictRow], cast: Cast) -> list[dict[str, Any]]:
    return admin.execute(
        "select * from public.expenses where owner_id = %s order by created_at, id", (cast.alicia.id,)
    ).fetchall()


def log_of(admin: Connection[DictRow], cast: Cast) -> list[dict[str, Any]]:
    return admin.execute(
        "select action, category, actor_id, actor_role, owner_id, entity_type, entity_id, metadata "
        "from public.activity_log where owner_id = %s and action like 'expense.%%' order by id",
        (cast.alicia.id,),
    ).fetchall()


def review_doc(pool: Pool, cast: Cast, *, suspected: bool = False, extraction: dict[str, Any] | None = None) -> Doc:
    doc = new_document(pool, cast.alicia)
    assert not call(pool, cast.alicia, "mark_document_uploaded", doc.id).error
    out = attempt(
        pool,
        cast.alicia,
        "select app.record_extraction(%s, %s, %s, 'trace-test', null)",
        (doc.id, Jsonb(extraction or GOOD_EXTRACTION), suspected),
    )
    assert not out.error, out.message
    return doc


def registered(pool: Pool, cast: Cast, **kw: Any) -> tuple[Doc, Any]:
    doc = review_doc(pool, cast)
    out = register(pool, cast.alicia, doc, **kw)
    assert not out.error, out.message
    return doc, out.rows[0]["id"]


def manual_expense(pool: Pool, cast: Cast, concept: str = "Cuota de autónomos", day: date = date(2026, 10, 1)) -> Any:
    out = call(pool, cast.alicia, "create_manual_expense", day, concept, "self_employed_fee", 29400)
    assert not out.error, out.message
    return out.rows[0]["create_manual_expense"]


def madrid_today(admin: Connection[DictRow]) -> date:
    found = admin.execute("select (now() at time zone 'Europe/Madrid')::date as today").fetchone()
    assert found is not None
    return found["today"]


def while_the_day_holds(admin: Connection[DictRow], check: Callable[[date], None]) -> None:
    """Ejecuta `check(hoy)` y lo repite si el día de Madrid cambió a mitad de la prueba (a las 00:00 de allí)."""
    for _ in range(3):
        today = madrid_today(admin)
        try:
            check(today)
        except AssertionError:
            if madrid_today(admin) == today:
                raise
            continue
        if madrid_today(admin) == today:
            return
    raise AssertionError("el día de Madrid cambió tres veces seguidas")


def no_secrets(entries: list[dict[str, Any]], *secrets: str) -> None:
    text = UUID.sub("", json.dumps([e["metadata"] for e in entries]))
    for secret in secrets:
        assert secret not in text, f"el registro de actividad contiene «{secret}»"


# --- registrar un gasto de un documento (AC-02) ----------------------------------------------------------------------------------


def test_registering_creates_the_expense_moves_the_document_and_logs_without_secrets(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = review_doc(app_pool, cast)
    original = doc_row(admin, doc)
    out = register(app_pool, cast.alicia, doc, category="software")
    assert not out.error, out.message
    expense_id = out.rows[0]["id"]

    row = expense_row(admin, expense_id)
    assert {k: row[k] for k in ("owner_id", "origin", "document_id", "category", "voided_at")} == {
        "owner_id": cast.alicia.id,
        "origin": "document",
        "document_id": doc.id,
        "category": "software",
        "voided_at": None,
    }
    assert row["expense_date"] == date(2026, 10, 15) and row["supplier_name"] == "Proveedor Sintético SL"
    assert (row["supplier_tax_id"], row["supplier_scope"], row["doc_type"]) == ("B00000042", "national", "full_invoice")
    assert (row["invoice_number"], row["invoice_number_key"]) == ("A-311", "A311")
    assert (row["base_cents"], row["vat_cents"], row["withholding_cents"], row["total_cents"]) == (
        10000,
        2100,
        0,
        12100,
    )
    assert row["tax_breakdown"] == LINES and row["deductible_vat"] is True and row["suspicion_acknowledged"] is False

    after = doc_row(admin, doc)
    assert after["status"] == "registered"
    for column in ("extraction", "review", "injection_suspected", "error_code", "storage_path"):
        assert after[column] == original[column], column

    (entry,) = log_of(admin, cast)
    assert (entry["category"], entry["actor_role"], entry["actor_id"], entry["owner_id"]) == (
        "data",
        "usuario",
        cast.alicia.id,
        cast.alicia.id,
    )
    assert (entry["action"], entry["entity_type"], entry["entity_id"]) == (
        "expense.registered",
        "expense",
        str(expense_id),
    )
    assert entry["metadata"] == {
        "expense_id": str(expense_id),
        "document_id": str(doc.id),
        "origin": "document",
        "category": "software",
        "acknowledged_suspicion": False,
    }
    no_secrets([entry], "Proveedor", "B00000042", "A-311", "12100", "10000", "2100")


@pytest.mark.parametrize("name", ["invoice_ok", "invoice_injection", "ticket_simplified"])
def test_what_the_validators_return_is_what_the_database_registers(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, name: str
) -> None:
    """La costura entre el hito 1 y la base: `RegistrableValues` -> `p_values` -> fila, sin que ningún campo se pierda."""
    reading = normalize_extraction(example_response(name))
    result = validate(from_stored(reading.extraction), ValidationContext(today=date(2026, 11, 7)))
    assert result.can_register and result.values is not None, [c for c in result.checks if not c.ok]
    expected = result.values
    doc = review_doc(app_pool, cast, suspected=reading.injection_suspected, extraction=reading.extraction)

    out = register(app_pool, cast.alicia, doc, payload=db_values(expected), acknowledged=reading.injection_suspected)
    assert not out.error, out.message
    row = expense_row(admin, out.rows[0]["id"])
    assert row["expense_date"] == expected.expense_date
    assert (row["supplier_name"], row["supplier_tax_id"], row["supplier_scope"]) == (
        expected.supplier_name,
        expected.supplier_tax_id,
        expected.supplier_scope,
    )
    assert (row["invoice_number"], row["invoice_number_key"], row["doc_type"]) == (
        expected.invoice_number,
        expected.invoice_number_key,  # la clave que calcula Python es la que genera la base
        expected.doc_type,
    )
    assert (row["base_cents"], row["vat_cents"], row["withholding_cents"], row["total_cents"]) == (
        expected.base_cents,
        expected.vat_cents,
        expected.withholding_cents,
        expected.total_cents,
    )
    assert row["tax_breakdown"] == db_values(expected)["tax_breakdown"]
    assert row["deductible_vat"] is expected.deductible_vat
    assert row["suspicion_acknowledged"] is reading.injection_suspected


def db_values(expected: RegistrableValues) -> dict[str, Any]:
    return {
        "expense_date": expected.expense_date.isoformat(),
        "supplier_name": expected.supplier_name,
        "supplier_tax_id": expected.supplier_tax_id,
        "supplier_scope": expected.supplier_scope,
        "invoice_number": expected.invoice_number,
        "doc_type": expected.doc_type,
        "base_cents": expected.base_cents,
        "vat_cents": expected.vat_cents,
        "withholding_cents": expected.withholding_cents,
        "total_cents": expected.total_cents,
        "tax_breakdown": [
            {"vat_rate": line.vat_rate, "base_cents": line.base_cents, "vat_cents": line.vat_cents}
            for line in expected.tax_lines
        ],
        "deductible_vat": expected.deductible_vat,
    }


def test_a_document_that_failed_to_read_and_was_filled_in_by_hand_can_be_registered(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """D-11."""
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "extraction_failed")
    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb({"total_cents": 12100})).error
    out = register(app_pool, cast.alicia, doc)
    assert not out.error, out.message
    after = doc_row(admin, doc)
    assert after["status"] == "registered" and after["extraction"] is None and after["review"] == {"total_cents": 12100}


@pytest.mark.parametrize("state", ["uploading", "processing", "discarded", "registered"])
def test_only_review_and_extraction_failed_can_be_registered(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str
) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), state)
    before, expenses, logged = doc_row(admin, doc), expenses_of(admin, cast), len(log_of(admin, cast))

    out = register(app_pool, cast.alicia, doc, payload=values(invoice_number="OTRA-1"))

    assert out.sqlstate == "P0001" and "document_wrong_state" in (out.message or ""), out.message
    assert doc_row(admin, doc) == before and expenses_of(admin, cast) == expenses and len(log_of(admin, cast)) == logged


# --- quién llama ---------------------------------------------------------------------------------------------------------------


def test_lock_document_returns_the_row_and_hides_foreign_and_discarded_ones(app_pool: Pool, cast: Cast) -> None:
    doc = review_doc(app_pool, cast)
    mine = attempt(app_pool, cast.alicia, "select * from app.lock_document(%s)", (doc.id,))
    assert not mine.error and mine.rows[0]["id"] == doc.id and mine.rows[0]["status"] == "review"
    assert mine.rows[0]["extraction"] == GOOD_EXTRACTION

    for person, target in ((cast.beto, doc.id), (cast.alicia, uuid.uuid4())):
        out = attempt(app_pool, person, "select * from app.lock_document(%s)", (target,))
        assert out.sqlstate == "P0001" and "document_not_found" in (out.message or "")

    assert not call(app_pool, cast.alicia, "discard_document", doc.id).error
    gone = attempt(app_pool, cast.alicia, "select * from app.lock_document(%s)", (doc.id,))
    assert gone.sqlstate == "P0001" and "document_not_found" in (gone.message or "")


def test_a_locked_document_cannot_be_changed_by_anyone_else_until_the_transaction_ends(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """Es lo que permite validar y registrar en una transacción sin que el documento cambie entre medias (T3-05)."""
    doc = review_doc(app_pool, cast)
    outcome: dict[str, Any] = {}
    waiter = threading.Thread(
        target=lambda: outcome.update(discard=call(app_pool, cast.alicia, "discard_document", doc.id))
    )
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select * from app.lock_document(%s)", (doc.id,))
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
        assert doc_row(admin, doc)["status"] == "review"
    waiter.join(timeout=15)
    assert still_waiting, "otra petición cambió el documento mientras estaba bloqueado"
    assert not outcome["discard"].error and doc_row(admin, doc)["status"] == "discarded"


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_use_any_expense_function(app_pool: Pool, cast: Cast, who: str) -> None:
    doc, expense_id = registered(app_pool, cast)
    actor = cast[who]
    attempts = {
        "lock_document": attempt(app_pool, actor, "select * from app.lock_document(%s)", (doc.id,)),
        "register": register(app_pool, actor, doc),
        "create_manual_expense": call(app_pool, actor, "create_manual_expense", date(2026, 10, 1), "x", "other", 100),
        "set_expense_category": call(app_pool, actor, "set_expense_category", expense_id, "training"),
        "void_expense": call(app_pool, actor, "void_expense", expense_id),
    }
    for name, out in attempts.items():
        assert out.sqlstate == "42501", f"{who}: {name} -> {out.sqlstate} {out.message}"


def test_another_user_gets_the_same_answer_as_for_something_that_does_not_exist(app_pool: Pool, cast: Cast) -> None:
    _, expense_id = registered(app_pool, cast)
    other = review_doc(app_pool, cast)
    foreign = register(app_pool, cast.beto, other)
    assert foreign.sqlstate == "P0001" and "document_not_found" in (foreign.message or "")
    for person, target in ((cast.beto, expense_id), (cast.alicia, uuid.uuid4())):
        for function, args in (("set_expense_category", (target, "training")), ("void_expense", (target,))):
            out = call(app_pool, person, function, *args)
            assert out.sqlstate == "P0001" and "expense_not_found" in (out.message or ""), (person.key, function)


# --- sospecha de instrucciones ocultas (AC-09) -----------------------------------------------------------------------------------


@pytest.mark.parametrize("acknowledged", [False, None])
def test_a_suspicious_document_is_not_registered_without_acknowledgement_in_the_database_either(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, acknowledged: bool | None
) -> None:
    doc = review_doc(app_pool, cast, suspected=True)
    before = doc_row(admin, doc)
    out = register(app_pool, cast.alicia, doc, acknowledged=acknowledged)
    assert out.sqlstate == "P0001" and "suspicion_not_acknowledged" in (out.message or ""), out.message
    assert doc_row(admin, doc) == before and expenses_of(admin, cast) == [] and log_of(admin, cast) == []


def test_an_acknowledged_suspicion_registers_and_leaves_a_mark(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = review_doc(app_pool, cast, suspected=True)
    out = register(app_pool, cast.alicia, doc, acknowledged=True)
    assert not out.error, out.message
    assert expense_row(admin, out.rows[0]["id"])["suspicion_acknowledged"] is True
    assert log_of(admin, cast)[0]["metadata"]["acknowledged_suspicion"] is True


def test_acknowledging_something_nobody_suspected_leaves_no_mark(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = review_doc(app_pool, cast)
    out = register(app_pool, cast.alicia, doc, acknowledged=True)
    assert not out.error, out.message
    assert expense_row(admin, out.rows[0]["id"])["suspicion_acknowledged"] is False
    assert log_of(admin, cast)[0]["metadata"]["acknowledged_suspicion"] is False


# --- lo que la función comprueba de `p_values` y de la fecha ---------------------------------------------------------------------


def without(key: str) -> dict[str, Any]:
    return {k: v for k, v in GOOD_VALUES.items() if k != key}


BAD_VALUES: list[tuple[Any, str]] = [
    (None, "values"),
    ([], "values"),
    ("texto", "values"),
    (5, "values"),
    ({}, "expense_date"),
    ({**GOOD_VALUES, "extra": 1}, "values"),
    ({**GOOD_VALUES, "invoice_number_key": "A311"}, "values"),  # la clave la genera la base: no se envía
    *[(without(key), key) for key in GOOD_VALUES],
    (values(supplier_name=5), "supplier_name"),
    (values(supplier_name=None), "supplier_name"),
    (values(supplier_tax_id=None), "supplier_tax_id"),
    (values(supplier_scope="world"), "supplier_scope"),
    (values(supplier_scope=None), "supplier_scope"),
    (values(doc_type=5), "doc_type"),
    (values(invoice_number=5), "invoice_number"),
    (values(expense_date="2026-1-5"), "expense_date"),
    (values(expense_date="15/10/2026"), "expense_date"),
    (values(expense_date="2026-02-30"), "expense_date"),
    (values(expense_date=20261015), "expense_date"),
    (values(expense_date="٢٠٢٦-١٠-١٥"), "expense_date"),
    (values(expense_date="2026-10-15" + chr(10)), "expense_date"),
    *[
        (values(**{key: bad}), key)
        for key in ("base_cents", "vat_cents", "withholding_cents", "total_cents")
        for bad in (100.5, "100", -1, 10**15, True, None)
    ],
    (values(tax_breakdown="x"), "tax_breakdown"),
    (values(tax_breakdown={}), "tax_breakdown"),
    (values(tax_breakdown=[{"vat_rate": "21", "base_cents": 9999, "vat_cents": 2100}]), "tax_breakdown"),
    (values(tax_breakdown=[]), "tax_breakdown"),
    (values(tax_breakdown=[*LINES, {"vat_rate": "0", "base_cents": 5.5, "vat_cents": 0}]), "tax_breakdown"),
    (values(tax_breakdown=[*LINES, {"vat_rate": "0", "base_cents": 0, "vat_cents": "0"}]), "tax_breakdown"),
    (values(deductible_vat="true"), "deductible_vat"),
    (values(deductible_vat=None), "deductible_vat"),
]


@pytest.mark.parametrize(
    ("payload", "field"), BAD_VALUES, ids=[f"{i}-{field}" for i, (_, field) in enumerate(BAD_VALUES)]
)
def test_malformed_values_are_refused_naming_the_field_and_nothing_changes(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, payload: Any, field: str
) -> None:
    doc = review_doc(app_pool, cast)
    before = doc_row(admin, doc)
    out = register(app_pool, cast.alicia, doc, payload=payload)
    assert out.sqlstate == "P0001" and "invalid_expense" in (out.message or ""), (out.sqlstate, out.message)
    assert out.detail == field
    assert doc_row(admin, doc) == before and expenses_of(admin, cast) == [] and log_of(admin, cast) == []


def test_a_missing_or_unknown_category_is_refused(app_pool: Pool, cast: Cast) -> None:
    doc = review_doc(app_pool, cast)
    missing = register(app_pool, cast.alicia, doc, category=None)
    assert missing.sqlstate == "P0001" and missing.detail == "category"
    unknown = register(app_pool, cast.alicia, doc, category="inventada")
    assert unknown.sqlstate == "22P02"


@pytest.mark.parametrize(
    ("change", "constraint"),
    [
        ({"doc_type": "other"}, "expenses_doc_type_known"),
        ({"total_cents": 12103}, "expenses_total_coherent"),
        ({"supplier_scope": "eu"}, "expenses_deductible_rule"),
        ({"supplier_tax_id": "b00000042"}, "expenses_tax_id_form"),
        ({"supplier_name": ""}, "expenses_supplier_name_length"),
        ({"invoice_number": "x" * 65}, "expenses_invoice_number_length"),
    ],
)
def test_what_the_function_lets_through_the_table_checks(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, change: dict[str, Any], constraint: str
) -> None:
    """La segunda pared (AC-16): la función no repite estas reglas, la tabla las impone."""
    doc = review_doc(app_pool, cast)
    before = doc_row(admin, doc)
    out = register(app_pool, cast.alicia, doc, payload=values(**change))
    assert out.sqlstate == "23514" and out.constraint == constraint, (out.sqlstate, out.constraint, out.message)
    assert doc_row(admin, doc) == before and expenses_of(admin, cast) == []


def test_the_date_must_be_between_2000_and_today_in_madrid(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    def check(today: date) -> None:
        cases = [
            (today, True),
            (today - timedelta(days=1), True),
            (date(2000, 1, 1), True),
            (today + timedelta(days=1), False),
            (today + timedelta(days=400), False),
            (date(1999, 12, 31), False),
        ]
        for day, fine in cases:
            doc = review_doc(app_pool, cast)
            out = register(
                app_pool,
                cast.alicia,
                doc,
                payload=values(expense_date=day.isoformat(), invoice_number=uuid.uuid4().hex[:10]),
            )
            if fine:
                assert not out.error, (day, out.message)
            else:
                assert out.sqlstate == "P0001" and out.detail == "expense_date", (day, out.sqlstate, out.message)

    while_the_day_holds(admin, check)


# --- gasto sin factura (AC-11) -----------------------------------------------------------------------------------------------------


def test_a_manual_expense_is_registered_without_vat_and_not_deductible(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    expense_id = manual_expense(app_pool, cast, "  Cuota de autónomos  ")
    row = expense_row(admin, expense_id)
    assert row["origin"] == "manual" and row["document_id"] is None and row["owner_id"] == cast.alicia.id
    assert row["supplier_name"] == "Cuota de autónomos", "el concepto se guarda recortado"
    assert (
        row["supplier_tax_id"],
        row["invoice_number"],
        row["invoice_number_key"],
        row["doc_type"],
        row["supplier_scope"],
    ) == (
        None,
        None,
        None,
        None,
        None,
    )
    assert (row["base_cents"], row["vat_cents"], row["withholding_cents"], row["total_cents"]) == (29400, 0, 0, 29400)
    assert row["tax_breakdown"] == [] and row["deductible_vat"] is False and row["category"] == "self_employed_fee"
    assert row["expense_date"] == date(2026, 10, 1) and row["suspicion_acknowledged"] is False

    (entry,) = log_of(admin, cast)
    assert entry["action"] == "expense.registered"
    assert entry["metadata"] == {
        "expense_id": str(expense_id),
        "document_id": None,
        "origin": "manual",
        "category": "self_employed_fee",
        "acknowledged_suspicion": False,
    }
    no_secrets([entry], "autónomos", "29400")


def test_the_edges_of_a_manual_expense_are_accepted(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    long = "x" * 200
    for concept, amount in ((long, 1), ("  " + long + "  ", 999999999999999), ("ñ" * 200, 5)):
        out = call(app_pool, cast.alicia, "create_manual_expense", date(2000, 1, 1), concept, "other", amount)
        assert not out.error, out.message
    assert len(expenses_of(admin, cast)) == 3


def test_a_manual_expense_dated_today_in_madrid_is_accepted_and_tomorrow_is_not(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    def check(today: date) -> None:
        assert not call(app_pool, cast.alicia, "create_manual_expense", today, "hoy", "other", 100).error
        tomorrow = call(
            app_pool, cast.alicia, "create_manual_expense", today + timedelta(days=1), "mañana", "other", 100
        )
        assert tomorrow.sqlstate == "P0001" and tomorrow.detail == "expense_date"

    while_the_day_holds(admin, check)


MANUAL = (date(2026, 10, 1), "Cuota", "other", 100)
BAD_MANUAL: list[tuple[tuple[Any, ...], str]] = [
    ((date(1999, 12, 31), *MANUAL[1:]), "expense_date"),
    ((None, *MANUAL[1:]), "expense_date"),
    ((MANUAL[0], "", *MANUAL[2:]), "concept"),
    ((MANUAL[0], "   ", *MANUAL[2:]), "concept"),
    ((MANUAL[0], None, *MANUAL[2:]), "concept"),
    ((MANUAL[0], "x" * 201, *MANUAL[2:]), "concept"),
    ((*MANUAL[:2], None, MANUAL[3]), "category"),
    ((*MANUAL[:3], 0), "amount_cents"),
    ((*MANUAL[:3], -100), "amount_cents"),
    ((*MANUAL[:3], None), "amount_cents"),
    ((*MANUAL[:3], 10**15), "amount_cents"),
    # con varios fallos a la vez, se informa del primero en el orden de los campos
    ((None, "", None, 0), "expense_date"),
    ((MANUAL[0], "", None, 0), "concept"),
    ((MANUAL[0], "ok", None, 0), "category"),
]


@pytest.mark.parametrize(("args", "field"), BAD_MANUAL, ids=[f"{i}-{field}" for i, (_, field) in enumerate(BAD_MANUAL)])
def test_a_manual_expense_with_a_bad_field_is_refused_naming_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, args: tuple[Any, ...], field: str
) -> None:
    out = call(app_pool, cast.alicia, "create_manual_expense", *args)
    assert out.sqlstate == "P0001" and "invalid_expense" in (out.message or "") and out.detail == field, (
        out.sqlstate,
        out.message,
        out.detail,
    )
    assert expenses_of(admin, cast) == [] and log_of(admin, cast) == []


def test_an_unknown_category_is_refused_for_a_manual_expense(app_pool: Pool, cast: Cast) -> None:
    out = call(app_pool, cast.alicia, "create_manual_expense", MANUAL[0], "x", "inventada", 100)
    assert out.sqlstate == "22P02"


# --- cambiar la categoría (AC-12) -----------------------------------------------------------------------------------------------


def test_changing_the_category_logs_once_and_changing_to_the_same_logs_nothing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    _, expense_id = registered(app_pool, cast, category="software")
    before = expense_row(admin, expense_id)

    assert not call(app_pool, cast.alicia, "set_expense_category", expense_id, "training").error
    changed = expense_row(admin, expense_id)
    assert changed["category"] == "training" and changed["updated_at"] > before["updated_at"]
    assert {k: v for k, v in changed.items() if k not in ("category", "updated_at")} == {
        k: v for k, v in before.items() if k not in ("category", "updated_at")
    }

    assert not call(app_pool, cast.alicia, "set_expense_category", expense_id, "training").error
    assert expense_row(admin, expense_id) == changed, "cambiar a la misma categoría no toca nada"

    entries = log_of(admin, cast)
    assert [e["action"] for e in entries] == ["expense.registered", "expense.category_changed"]
    assert entries[1]["metadata"] == {
        "expense_id": str(expense_id),
        "from_category": "software",
        "to_category": "training",
    }


def test_the_category_of_a_manual_expense_can_change_too(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    expense_id = manual_expense(app_pool, cast)
    assert not call(app_pool, cast.alicia, "set_expense_category", expense_id, "other").error
    assert expense_row(admin, expense_id)["category"] == "other"


def test_setting_the_category_refuses_a_missing_unknown_or_voided_one(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    _, expense_id = registered(app_pool, cast)
    missing = call(app_pool, cast.alicia, "set_expense_category", expense_id, None)
    assert missing.sqlstate == "P0001" and missing.detail == "category"
    assert call(app_pool, cast.alicia, "set_expense_category", expense_id, "inventada").sqlstate == "22P02"

    assert not call(app_pool, cast.alicia, "void_expense", expense_id).error
    voided = expense_row(admin, expense_id)
    out = call(app_pool, cast.alicia, "set_expense_category", expense_id, "training")
    assert out.sqlstate == "P0001" and "expense_wrong_state" in (out.message or "")
    assert expense_row(admin, expense_id) == voided


# --- anular (AC-13) -------------------------------------------------------------------------------------------------------------------


def test_voiding_returns_the_document_to_review_and_it_can_be_registered_again(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = review_doc(app_pool, cast)
    corrections = {"supplier_name": "Corregido", "total_cents": 12100}
    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb(corrections)).error
    first = register(app_pool, cast.alicia, doc).rows[0]["id"]
    original = doc_row(admin, doc)

    for function, args in (
        ("discard_document", (doc.id,)),
        ("save_document_review", (doc.id, Jsonb({"total_cents": 1}))),
    ):
        blocked = call(app_pool, cast.alicia, function, *args)
        assert blocked.sqlstate == "P0001" and "document_wrong_state" in (blocked.message or ""), function

    out = call(app_pool, cast.alicia, "void_expense", first)
    assert not out.error, out.message
    assert out.rows[0]["void_expense"] == "review"
    back = doc_row(admin, doc)
    assert back["status"] == "review" and back["review"] == corrections and back["extraction"] == original["extraction"]
    assert back["injection_suspected"] == original["injection_suspected"]
    assert expense_row(admin, first)["voided_at"] is not None

    second = register(app_pool, cast.alicia, doc)
    assert not second.error, second.message
    assert second.rows[0]["id"] != first
    live = [e for e in expenses_of(admin, cast) if e["voided_at"] is None]
    assert [e["id"] for e in live] == [second.rows[0]["id"]] and len(expenses_of(admin, cast)) == 2

    entries = log_of(admin, cast)
    assert [e["action"] for e in entries] == ["expense.registered", "expense.voided", "expense.registered"]
    assert entries[1]["metadata"] == {"expense_id": str(first), "origin": "document"}


def test_a_document_that_was_never_read_goes_back_to_extraction_failed_keeping_its_reason(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "extraction_failed")
    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb({"total_cents": 12100})).error
    expense_id = register(app_pool, cast.alicia, doc).rows[0]["id"]

    out = call(app_pool, cast.alicia, "void_expense", expense_id)
    assert not out.error, out.message
    assert out.rows[0]["void_expense"] == "extraction_failed"
    back = doc_row(admin, doc)
    assert (back["status"], back["error_code"], back["extraction"]) == ("extraction_failed", "unreadable", None)
    assert back["review"] == {"total_cents": 12100}


def test_a_voided_manual_expense_just_stops_counting(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    expense_id = manual_expense(app_pool, cast)
    out = call(app_pool, cast.alicia, "void_expense", expense_id)
    assert not out.error and out.rows[0]["void_expense"] is None
    assert expense_row(admin, expense_id)["voided_at"] is not None
    assert log_of(admin, cast)[-1]["metadata"] == {"expense_id": str(expense_id), "origin": "manual"}
    again = call(app_pool, cast.alicia, "void_expense", expense_id)
    assert again.sqlstate == "P0001" and "expense_wrong_state" in (again.message or "")


def test_voiding_twice_changes_nothing_the_second_time(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    doc, expense_id = registered(app_pool, cast)
    assert not call(app_pool, cast.alicia, "void_expense", expense_id).error
    expense, document, logged = expense_row(admin, expense_id), doc_row(admin, doc), len(log_of(admin, cast))

    again = call(app_pool, cast.alicia, "void_expense", expense_id)
    assert again.sqlstate == "P0001" and "expense_wrong_state" in (again.message or "")
    assert (
        expense_row(admin, expense_id) == expense
        and doc_row(admin, doc) == document
        and len(log_of(admin, cast)) == logged
    )


def test_after_voiding_the_document_can_be_discarded_again(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc, expense_id = registered(app_pool, cast)
    assert not call(app_pool, cast.alicia, "void_expense", expense_id).error
    assert not call(app_pool, cast.alicia, "discard_document", doc.id).error
    assert doc_row(admin, doc)["status"] == "discarded"


def test_the_same_invoice_can_be_registered_again_once_the_first_one_is_voided(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """AC-08."""
    _, first = registered(app_pool, cast)
    second_doc = review_doc(app_pool, cast)
    duplicate = register(
        app_pool, cast.alicia, second_doc, payload=values(supplier_tax_id="B00000042", invoice_number="a311")
    )
    assert duplicate.sqlstate == "23505" and duplicate.constraint == "expenses_duplicate_invoice"
    assert doc_row(admin, second_doc)["status"] == "review" and len(expenses_of(admin, cast)) == 1

    assert not call(app_pool, cast.alicia, "void_expense", first).error
    assert not register(app_pool, cast.alicia, second_doc, payload=values(invoice_number="a311")).error


# --- documents_guard ampliado (AC-16) ----------------------------------------------------------------------------------------------


def live_expense_for(admin: Connection[DictRow], cast: Cast, doc: Doc, **overrides: Any) -> Any:
    row = admin.execute(INSERT, params(cast.alicia, doc, **overrides)).fetchone()
    assert row is not None
    return row["id"]


@pytest.mark.parametrize("state", ["review", "extraction_failed"])
def test_a_document_cannot_become_registered_without_a_live_expense(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str
) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), state)
    with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
        admin.execute("update public.documents set status = 'registered' where id = %s", (doc.id,))
    live_expense_for(admin, cast, doc, voided=datetime.now(UTC))  # un gasto ya anulado no cuenta como vivo
    with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
        admin.execute("update public.documents set status = 'registered' where id = %s", (doc.id,))
    assert doc_row(admin, doc)["status"] == state


@pytest.mark.parametrize("state", ["review", "extraction_failed"])
def test_a_live_expense_allows_the_document_to_become_registered(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str
) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), state)
    live_expense_for(admin, cast, doc)
    admin.execute("update public.documents set status = 'registered' where id = %s", (doc.id,))
    assert doc_row(admin, doc)["status"] == "registered"


@pytest.mark.parametrize(
    "statement",
    [
        "update public.documents set status = 'processing' where id = %s",
        "update public.documents set status = 'uploading' where id = %s",
        "update public.documents set status = 'discarded' where id = %s",
        "update public.documents set status = 'review' where id = %s",  # sin anular el gasto
        "update public.documents set status = 'extraction_failed', error_code = 'timeout' where id = %s",
        "update public.documents set review = '{}' where id = %s",  # sin cambio de estado
        "update public.documents set error_code = 'timeout' where id = %s",
        "update public.documents set injection_suspected = true where id = %s",
    ],
)
def test_a_registered_document_only_leaves_that_state_by_voiding_its_expense(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, statement: str
) -> None:
    doc, _ = registered(app_pool, cast)
    before = doc_row(admin, doc)
    with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
        admin.execute(statement, (doc.id,))
    assert doc_row(admin, doc) == before


def test_an_expense_voided_in_an_earlier_transaction_does_not_free_the_document(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc, expense_id = registered(app_pool, cast)
    admin.execute("update public.expenses set voided_at = now() where id = %s", (expense_id,))  # una transacción propia
    for status in ("review", "extraction_failed"):
        with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
            admin.execute("update public.documents set status = %s where id = %s", (status, doc.id))
    assert doc_row(admin, doc)["status"] == "registered"


def test_voiding_in_the_same_transaction_frees_the_document(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc, expense_id = registered(app_pool, cast)
    with admin.transaction():
        admin.execute("update public.expenses set voided_at = now() where id = %s", (expense_id,))
        admin.execute("update public.documents set status = 'review' where id = %s", (doc.id,))
    assert doc_row(admin, doc)["status"] == "review"


def test_a_document_with_another_live_expense_does_not_go_back(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """El índice impide dos gastos vivos de un documento; aun así, el trigger lo mira por su cuenta (se quita el índice un momento)."""
    doc, expense_id = registered(app_pool, cast)
    with admin.transaction(force_rollback=True):
        admin.execute("drop index public.expenses_one_active_per_document")
        live_expense_for(admin, cast, doc, number="OTRO-1")
        admin.execute("update public.expenses set voided_at = now() where id = %s", (expense_id,))
        with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
            admin.execute("update public.documents set status = 'review' where id = %s", (doc.id,))
    assert doc_row(admin, doc)["status"] == "registered"
    assert admin.execute("select to_regclass('public.expenses_one_active_per_document')::text as i").fetchone() == {
        "i": "expenses_one_active_per_document"
    }


@pytest.mark.parametrize("status", ["discarded", "processing", "uploading", "registered"])
def test_voiding_in_the_same_transaction_only_frees_the_document_towards_revision(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, status: str
) -> None:
    doc, expense_id = registered(app_pool, cast)
    with admin.transaction(force_rollback=True):
        admin.execute("update public.expenses set voided_at = now() where id = %s", (expense_id,))
        with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
            admin.execute("update public.documents set status = %s where id = %s", (status, doc.id))
    assert doc_row(admin, doc)["status"] == "registered"


@pytest.mark.parametrize("state", ["uploading", "processing", "discarded"])
def test_only_a_document_in_review_can_become_registered_even_with_a_live_expense(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str
) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), state)
    live_expense_for(admin, cast, doc)
    with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
        admin.execute("update public.documents set status = 'registered' where id = %s", (doc.id,))
    assert doc_row(admin, doc)["status"] == state


# --- concurrencia (T3-05) ---------------------------------------------------------------------------------------------------------------


def test_two_documents_with_the_same_invoice_leave_exactly_one_expense(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """AC-08 · el índice único lo decide aunque las dos peticiones lleguen a la vez: la segunda espera a la primera y pierde."""
    first, second = review_doc(app_pool, cast), review_doc(app_pool, cast)
    outcome: dict[str, Any] = {}
    waiter = threading.Thread(target=lambda: outcome.update(second=register(app_pool, cast.alicia, second)))
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute(
            "select app.register_expense_from_document(%s, 'software', %s, false)", (first.id, Jsonb(GOOD_VALUES))
        )  # aún sin confirmar
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=15)

    assert still_waiting, "la segunda petición no esperó a la primera"
    assert outcome["second"].sqlstate == "23505" and outcome["second"].constraint == "expenses_duplicate_invoice"
    assert [e["document_id"] for e in expenses_of(admin, cast)] == [first.id]
    assert doc_row(admin, second)["status"] == "review" and doc_row(admin, first)["status"] == "registered"


def test_two_confirmations_of_the_same_document_register_it_once(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = review_doc(app_pool, cast)
    outcome: dict[str, Any] = {}
    waiter = threading.Thread(target=lambda: outcome.update(second=register(app_pool, cast.alicia, doc)))
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select * from app.lock_document(%s)", (doc.id,))
        conn.execute(
            "select app.register_expense_from_document(%s, 'software', %s, false)", (doc.id, Jsonb(GOOD_VALUES))
        )
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=15)

    assert still_waiting
    assert outcome["second"].sqlstate == "P0001" and "document_wrong_state" in (outcome["second"].message or "")
    assert len(expenses_of(admin, cast)) == 1 and len(log_of(admin, cast)) == 1


def test_two_voids_of_the_same_expense_act_once(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    doc, expense_id = registered(app_pool, cast)
    outcome: dict[str, Any] = {}
    waiter = threading.Thread(
        target=lambda: outcome.update(second=call(app_pool, cast.alicia, "void_expense", expense_id))
    )
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select app.void_expense(%s)", (expense_id,))
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=15)

    assert still_waiting
    assert outcome["second"].sqlstate == "P0001" and "expense_wrong_state" in (outcome["second"].message or "")
    assert doc_row(admin, doc)["status"] == "review"
    assert [e["action"] for e in log_of(admin, cast)] == ["expense.registered", "expense.voided"]


@pytest.mark.parametrize("second", ["void_expense", "set_expense_category"])
def test_a_manual_expense_is_locked_while_it_is_being_voided(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, second: str
) -> None:
    """Un gasto sin factura no tiene documento que serialice las operaciones: lo hace el cerrojo del propio gasto."""
    expense_id = manual_expense(app_pool, cast)
    args = (expense_id, "training") if second == "set_expense_category" else (expense_id,)
    outcome: dict[str, Any] = {}
    waiter = threading.Thread(target=lambda: outcome.update(second=call(app_pool, cast.alicia, second, *args)))
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select app.void_expense(%s)", (expense_id,))
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=15)

    assert still_waiting, "la segunda operación no esperó a que terminara la anulación"
    assert outcome["second"].sqlstate == "P0001" and "expense_wrong_state" in (outcome["second"].message or "")
    assert expense_row(admin, expense_id)["category"] == "self_employed_fee"


# --- el registro de actividad (AC-17) ----------------------------------------------------------------------------------------------------


def test_the_whole_flow_leaves_only_identifiers_categories_and_marks(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    secret = values(supplier_name="Secreto Proveedor 777", invoice_number="SECRETO-9911", supplier_tax_id="B00000075")
    doc = review_doc(app_pool, cast)
    expense_id = register(app_pool, cast.alicia, doc, payload=secret).rows[0]["id"]
    call(app_pool, cast.alicia, "set_expense_category", expense_id, "advisory")
    call(app_pool, cast.alicia, "void_expense", expense_id)
    manual = manual_expense(app_pool, cast, "Concepto secreto 29400")
    call(app_pool, cast.alicia, "void_expense", manual)

    entries = log_of(admin, cast)
    assert [e["action"] for e in entries] == [
        "expense.registered",
        "expense.category_changed",
        "expense.voided",
        "expense.registered",
        "expense.voided",
    ]
    for entry in entries:
        assert (entry["category"], entry["actor_role"], entry["entity_type"]) == ("data", "usuario", "expense")
        assert entry["actor_id"] == entry["owner_id"] == cast.alicia.id
    no_secrets(entries, "Secreto", "SECRETO", "B00000075", "29400", "12100", "10000", "2100", "777", "9911")
