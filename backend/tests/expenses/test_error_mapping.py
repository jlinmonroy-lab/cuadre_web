"""Errores de la base de datos -> `problem+json` (SPEC-W-003 §5.3, Anexo B.3). Se provocan los errores REALES de las funciones `app.*`.

Lo que NO se traduce importa tanto como lo que sí: un campo de `invalid_expense` que la API habría validado antes, una CHECK o una categoría
fuera de la lista solo pueden aparecer por un fallo nuestro, y un 4xx lo disfrazaría.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction
from cuadre.expenses import repository
from tests.support import GOOD_EXTRACTION, GOOD_VALUES, Cast, Pool, advance, new_document, register, values


def raised(pool: Pool, person: Any, sql: str, params: tuple[Any, ...] = ()) -> psycopg.Error:
    with pytest.raises(psycopg.Error) as caught, user_transaction(pool, person.id) as conn:
        conn.execute(sql, params)
    return caught.value


def translated(error: psycopg.Error | Any) -> ProblemError:
    problem = repository.translate_db_error(error)
    assert problem is not None
    return problem


def review_document(pool: Pool, cast: Cast, *, suspected: bool = False) -> Any:
    if not suspected:
        return advance(pool, cast.alicia, new_document(pool, cast.alicia), "review")
    doc = new_document(pool, cast.alicia)
    advance(pool, cast.alicia, doc, "processing")
    with user_transaction(pool, cast.alicia.id) as conn:
        conn.execute("select app.record_extraction(%s, %s, true, 'trace-test', null)", (doc.id, Jsonb(GOOD_EXTRACTION)))
    return doc


def manual_error(pool: Pool, cast: Cast, *args: Any) -> psycopg.Error:
    return raised(pool, cast.alicia, "select app.create_manual_expense(%s, %s, %s, %s)", args)


def registered_id(pool: Pool, cast: Cast) -> Any:
    doc = review_document(pool, cast)
    out = register(pool, cast.alicia, doc)
    assert not out.error, out.message
    return out.rows[0]["id"]


# --- los que sí se traducen -------------------------------------------------------------------------------------------------------


def test_expense_not_found_is_404(app_pool: Pool, cast: Cast) -> None:
    problem = translated(raised(app_pool, cast.alicia, "select app.void_expense(gen_random_uuid())"))
    assert (problem.status, problem.code) == (404, "expense_not_found")


def test_a_foreign_expense_is_also_404(app_pool: Pool, cast: Cast) -> None:
    expense_id = registered_id(app_pool, cast)
    problem = translated(raised(app_pool, cast.beto, "select app.void_expense(%s)", (expense_id,)))
    assert (problem.status, problem.code) == (404, "expense_not_found")


def test_a_voided_expense_is_409(app_pool: Pool, cast: Cast) -> None:
    expense_id = registered_id(app_pool, cast)
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select app.void_expense(%s)", (expense_id,))
    for sql, params in (
        ("select app.void_expense(%s)", (expense_id,)),
        ("select app.set_expense_category(%s, 'other')", (expense_id,)),
    ):
        problem = translated(raised(app_pool, cast.alicia, sql, params))
        assert (problem.status, problem.code) == (409, "expense_wrong_state"), sql


def test_an_unacknowledged_suspicion_is_422(app_pool: Pool, cast: Cast) -> None:
    doc = review_document(app_pool, cast, suspected=True)
    error = raised(
        app_pool,
        cast.alicia,
        "select app.register_expense_from_document(%s, 'software', %s, false)",
        (doc.id, Jsonb(GOOD_VALUES)),
    )
    problem = translated(error)
    assert (problem.status, problem.code) == (422, "suspicion_not_acknowledged")


@pytest.mark.parametrize(
    ("args", "field"),
    [
        ((date.today() + timedelta(days=2), "x", "other", 100), "expense_date"),
        ((date(1999, 12, 31), "x", "other", 100), "expense_date"),
        ((date(2026, 10, 1), "", "other", 100), "concept"),
        ((date(2026, 10, 1), "x", None, 100), "category"),
        ((date(2026, 10, 1), "x", "other", 0), "amount_cents"),
    ],
)
def test_invalid_expense_carries_the_field_from_the_database(
    app_pool: Pool, cast: Cast, args: tuple[Any, ...], field: str
) -> None:
    problem = translated(manual_error(app_pool, cast, *args))
    assert (problem.status, problem.code) == (422, "invalid_expense")
    assert problem.extra == {"field": field}
    assert problem.detail.endswith("."), "un mensaje para la persona, en español"


def test_a_duplicate_invoice_is_409_duplicate_expense(app_pool: Pool, cast: Cast) -> None:
    registered_id(app_pool, cast)
    other = review_document(app_pool, cast)
    error = raised(
        app_pool,
        cast.alicia,
        "select app.register_expense_from_document(%s, 'software', %s, false)",
        (other.id, Jsonb(values(invoice_number="a311"))),
    )
    assert error.sqlstate == "23505" and error.diag.constraint_name == "expenses_duplicate_invoice"
    problem = translated(error)
    assert (problem.status, problem.code) == (409, "duplicate_expense")


def test_the_race_on_one_document_is_a_wrong_state_not_a_duplicate() -> None:
    """`expenses_one_active_per_document` solo salta si dos confirmaciones del mismo documento llegan al índice a la vez."""
    stub = SimpleNamespace(
        sqlstate="23505",
        diag=SimpleNamespace(
            constraint_name="expenses_one_active_per_document", message_primary=None, message_detail=None
        ),
    )
    problem = translated(stub)
    assert (problem.status, problem.code) == (409, "document_wrong_state")


def test_document_errors_and_roles_keep_their_translations(app_pool: Pool, cast: Cast) -> None:
    doc = new_document(app_pool, cast.alicia)
    wrong_state = translated(
        raised(
            app_pool,
            cast.alicia,
            "select app.register_expense_from_document(%s, 'software', %s, false)",
            (doc.id, Jsonb(GOOD_VALUES)),
        )
    )
    assert (wrong_state.status, wrong_state.code) == (409, "document_wrong_state")

    ghost = translated(
        raised(
            app_pool,
            cast.alicia,
            "select app.register_expense_from_document(gen_random_uuid(), 'software', %s, false)",
            (Jsonb(GOOD_VALUES),),
        )
    )
    assert (ghost.status, ghost.code) == (404, "document_not_found")

    forbidden = translated(
        raised(app_pool, cast.gina, "select app.create_manual_expense(%s, 'x', 'other', 100)", (date(2026, 10, 1),))
    )
    assert (forbidden.status, forbidden.code) == (403, "forbidden")


# --- los que no se disfrazan --------------------------------------------------------------------------------------------------------


def test_errors_that_the_api_should_have_prevented_are_not_disguised(app_pool: Pool, cast: Cast) -> None:
    doc = review_document(app_pool, cast)

    def register_error(payload: Any, category: str = "software") -> psycopg.Error:
        return raised(
            app_pool,
            cast.alicia,
            "select app.register_expense_from_document(%s, %s, %s, false)",
            (doc.id, category, None if payload is None else Jsonb(payload)),
        )

    for payload, detail in (
        (None, "values"),
        ({**GOOD_VALUES, "base_cents": 100.5}, "base_cents"),
        ({"x": 1}, "values"),
    ):
        error = register_error(payload)
        assert error.diag.message_primary == "invalid_expense" and error.diag.message_detail == detail
        assert repository.translate_db_error(error) is None, detail

    check = register_error(values(total_cents=12103))
    assert check.sqlstate == "23514" and repository.translate_db_error(check) is None

    category = register_error(GOOD_VALUES, "inventada")
    assert category.sqlstate == "22P02" and repository.translate_db_error(category) is None


def test_an_unknown_code_or_an_unknown_index_is_not_translated() -> None:
    unknown_index = SimpleNamespace(
        sqlstate="23505", diag=SimpleNamespace(constraint_name="otro_indice", message_primary=None, message_detail=None)
    )
    unknown_message = SimpleNamespace(
        sqlstate="P0001",
        diag=SimpleNamespace(constraint_name=None, message_primary="expense_already_voided", message_detail=None),
    )
    assert repository.translate_db_error(unknown_index) is None  # type: ignore[arg-type]
    assert repository.translate_db_error(unknown_message) is None  # type: ignore[arg-type]
