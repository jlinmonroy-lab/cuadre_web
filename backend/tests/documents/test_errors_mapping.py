"""Errores de la base de datos -> `problem+json` (SPEC-W-002 §5.1, Anexo B.3). Se provocan los errores REALES de las funciones `app.*`."""

import psycopg
import pytest
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction
from cuadre.documents import repository
from tests.support import Cast, Pool, advance, new_document


def raised(pool: Pool, person: object, sql: str, params: tuple = ()) -> psycopg.Error:
    with pytest.raises(psycopg.Error) as caught, user_transaction(pool, person.id) as conn:  # type: ignore[attr-defined]
        conn.execute(sql, params)
    return caught.value


def translated(error: psycopg.Error) -> ProblemError:
    problem = repository.translate_db_error(error)
    assert problem is not None
    return problem


def test_document_not_found_is_404(app_pool: Pool, cast: Cast) -> None:
    error = raised(app_pool, cast.alicia, "select app.discard_document(gen_random_uuid())")
    problem = translated(error)
    assert (problem.status, problem.code) == (404, "document_not_found")


def test_a_foreign_document_is_also_404(app_pool: Pool, cast: Cast) -> None:
    doc = new_document(app_pool, cast.beto)
    problem = translated(raised(app_pool, cast.alicia, "select app.discard_document(%s)", (doc.id,)))
    assert (problem.status, problem.code) == (404, "document_not_found")


def test_document_wrong_state_is_409(app_pool: Pool, cast: Cast) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "review")
    problem = translated(raised(app_pool, cast.alicia, "select app.mark_document_uploaded(%s)", (doc.id,)))
    assert (problem.status, problem.code) == (409, "document_wrong_state")


def test_too_many_processing_is_429_with_retry_after(app_pool: Pool, cast: Cast) -> None:
    for _ in range(5):
        advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "processing")
    problem = translated(
        raised(app_pool, cast.alicia, "select app.create_document('a.pdf', 'application/pdf', 10, 'file')")
    )
    assert (problem.status, problem.code) == (429, "too_many_processing")
    assert problem.headers == {"Retry-After": "10"}


def test_a_role_that_is_not_usuario_is_403(app_pool: Pool, cast: Cast) -> None:
    problem = translated(
        raised(app_pool, cast.gina, "select app.create_document('a.pdf', 'application/pdf', 10, 'file')")
    )
    assert (problem.status, problem.code) == (403, "forbidden")


def test_errors_that_the_api_should_have_prevented_are_not_disguised(app_pool: Pool, cast: Cast) -> None:
    """`invalid_review` y las CHECK solo pueden aparecer si la validación de forma falló antes: son un fallo nuestro (500), no un 4xx."""
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "review")
    null_review = raised(app_pool, cast.alicia, "select app.save_document_review(%s, null)", (doc.id,))
    assert null_review.diag.message_primary == "invalid_review"
    assert repository.translate_db_error(null_review) is None

    float_amount = raised(
        app_pool, cast.alicia, "select app.save_document_review(%s, %s)", (doc.id, Jsonb({"total_cents": 12.5}))
    )
    assert float_amount.sqlstate == "23514"
    assert repository.translate_db_error(float_amount) is None


def test_an_unrecognised_application_error_is_not_translated(app_pool: Pool, cast: Cast) -> None:
    error = raised(app_pool, cast.alicia, "select app.fail_extraction(gen_random_uuid(), 'timeout')")
    assert translated(error).code == "document_not_found"  # sí reconocido
    other = raised(app_pool, cast.alicia, "select 1 / 0")
    assert repository.translate_db_error(other) is None
