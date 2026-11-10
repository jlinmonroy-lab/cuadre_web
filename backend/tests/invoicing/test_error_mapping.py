"""§5.2 y B.3 «Para el hito 3» · La traducción de los errores de la base a `problem+json`, con errores REALES de PostgreSQL.

Cada código estable de las funciones `app.*` tiene su problema (código, estado, campo y texto en español). Lo que no es nuestro (un campo de
construcción, otro estado SQL) no se traduce: se propaga y la API lo responde como un 500 sin detalles.
"""

import uuid
from datetime import date
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction
from cuadre.invoicing import repository
from cuadre.tax import Standing
from tests.rls.invoices_support import D1, D2, Ready, client, issue, made, ready, rectification_terms, series, terms
from tests.support import Cast, Person, Pool

VALID_TERMS = terms()
STANDING = Standing(
    100_000, 21_000, 15_000
)  # lo vigente de la factura de las pruebas: base 100.000 al 21 % con retención del 15 %


def raised(pool: Pool, person: Person, sql: str, params: Any = None) -> psycopg.Error:
    with pytest.raises(psycopg.Error) as info, user_transaction(pool, person.id) as conn:
        conn.execute(sql, params)
    return info.value


def issuing(pool: Pool, person: Person, client_id: object, series_id: object, **over: Any) -> psycopg.Error:
    args = {"when": D1, "concept": "Servicios", "base": 100_000, "given": VALID_TERMS, **over}
    return raised(
        pool,
        person,
        "select app.issue_invoice(%s, %s, %s, %s, %s, %s)",
        (client_id, series_id, args["when"], args["concept"], args["base"], Jsonb(args["given"])),
    )


def rectifying(
    pool: Pool, person: Person, original: object, corrected: int = 80_000, when: date = D2, **over: Any
) -> psycopg.Error:
    given = over.get("given", rectification_terms(STANDING, corrected))
    return raised(
        pool,
        person,
        "select app.issue_rectifying_invoice(%s, 'Motivo', %s, %s, %s)",
        (original, corrected, when, Jsonb(given)),
    )


def problem(exc: psycopg.Error) -> ProblemError:
    translated = repository.translate_db_error(exc)
    assert translated is not None, (exc.sqlstate, exc.diag.message_primary, exc.diag.message_detail)
    return translated


@pytest.fixture
def r(admin: Connection[DictRow], cast: Cast) -> Ready:
    return ready(admin, cast.alicia)


def test_a_manager_is_forbidden(app_pool: Pool, cast: Cast, r: Ready) -> None:
    p = problem(issuing(app_pool, cast.gina, r.clients[("national", "business")], r.series))
    assert (p.status, p.code) == (403, "forbidden")


def test_a_missing_client_and_a_missing_series_are_field_errors(app_pool: Pool, cast: Cast, r: Ready) -> None:
    unknown = uuid.uuid4()
    p = problem(issuing(app_pool, cast.alicia, unknown, r.series))
    assert (p.status, p.code, p.extra["fields"][0]["field"]) == (422, "invalid_invoice", "client_id")
    p = problem(issuing(app_pool, cast.alicia, r.clients[("national", "business")], unknown))
    assert (p.status, p.code, p.extra["fields"][0]["field"]) == (422, "invalid_invoice", "series_id")


def test_an_archived_client_and_a_client_without_address_are_not_billable(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast, r: Ready
) -> None:
    archived = client(admin, cast.alicia, archived=True)
    p = problem(issuing(app_pool, cast.alicia, archived, r.series))
    assert (p.status, p.code, p.extra["field"]) == (409, "client_not_billable", "client_id")
    no_address = client(admin, cast.alicia, address=None)
    p = problem(issuing(app_pool, cast.alicia, no_address, r.series))
    assert (p.status, p.code, p.extra["field"]) == (409, "client_not_billable", "address")


def test_an_incomplete_profile_lists_what_is_missing_with_labels(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast, r: Ready
) -> None:
    admin.execute(
        "update public.business_profiles set legal_name = null, tax_id = null where owner_id = %s", (cast.alicia.id,)
    )
    p = problem(issuing(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    assert (p.status, p.code) == (422, "profile_incomplete")
    assert p.extra["missing"] == [
        {"field": "legal_name", "label": "Nombre o razón social"},
        {"field": "tax_id", "label": "NIF"},
    ]


def test_a_missing_retention_is_a_422(admin: Connection[DictRow], app_pool: Pool, cast: Cast, r: Ready) -> None:
    admin.execute("update public.business_profiles set irpf_rate = null where owner_id = %s", (cast.alicia.id,))
    p = problem(issuing(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    assert (p.status, p.code) == (422, "irpf_rate_missing")


def test_a_date_out_of_order_carries_the_reference_date(app_pool: Pool, cast: Cast, r: Ready) -> None:
    cid = r.clients[("national", "business")]
    made(issue(app_pool, cast.alicia, cid, r.series, when=D2))
    p = problem(issuing(app_pool, cast.alicia, cid, r.series, when=D1))
    assert (p.status, p.code, p.extra["field"]) == (409, "invoice_date_out_of_order", "issue_date")
    assert "09/03/2026" in p.detail


def test_a_serie_at_the_last_number_is_exhausted(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    last = series(admin, cast.alicia, "FIN", first=999_999)
    cid = r.clients[("national", "business")]
    made(issue(app_pool, cast.alicia, cid, last))
    p = problem(issuing(app_pool, cast.alicia, cid, last))
    assert (p.status, p.code) == (409, "series_exhausted")


@pytest.mark.parametrize(
    ("over", "field"),
    [({"when": date(1999, 12, 31)}, "issue_date"), ({"concept": "a"}, "concept"), ({"base": 0}, "base_cents")],
)
def test_the_three_fields_a_person_can_see_are_field_errors(
    app_pool: Pool, cast: Cast, r: Ready, over: dict[str, Any], field: str
) -> None:
    p = problem(issuing(app_pool, cast.alicia, r.clients[("national", "business")], r.series, **over))
    assert (p.status, p.code, p.extra["fields"][0]["field"]) == (422, "invalid_invoice", field)


def test_a_construction_error_is_not_translated(app_pool: Pool, cast: Cast, r: Ready) -> None:
    """Un campo de las condiciones mal construido es un error NUESTRO: la API lo responde como un 500 sin detalles."""
    exc = issuing(
        app_pool, cast.alicia, r.clients[("national", "business")], r.series, given={**VALID_TERMS, "total_cents": 1}
    )
    assert (exc.diag.message_primary, exc.diag.message_detail) == ("invalid_invoice", "total_cents")
    assert repository.translate_db_error(exc) is None


def test_rectification_errors(app_pool: Pool, cast: Cast, r: Ready) -> None:
    original = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    exceeds = rectifying(
        app_pool, cast.alicia, original, corrected=100_001, given={"vat_cents": 0, "irpf_cents": 0, "total_cents": 0}
    )
    p = problem(exceeds)
    assert (p.status, p.code, p.extra["field"]) == (409, "rectification_exceeds", "corrected_base_cents")
    assert repository.is_stale_rectification(exceeds) is True

    with user_transaction(app_pool, cast.alicia.id) as conn:
        row = conn.execute(
            "select app.issue_rectifying_invoice(%s, 'Motivo', 80000, %s, %s) as id",
            (original, D2, Jsonb(rectification_terms(STANDING, 80_000))),
        ).fetchone()
    assert row is not None
    p = problem(rectifying(app_pool, cast.alicia, row["id"]))
    assert (p.status, p.code) == (409, "invoice_not_rectifiable")


def test_a_stale_rectification_is_recognized_only_by_its_own_signs(app_pool: Pool, cast: Cast, r: Ready) -> None:
    original = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    wrong_total = rectifying(
        app_pool, cast.alicia, original, given={"vat_cents": -4200, "irpf_cents": -3000, "total_cents": -1}
    )
    assert repository.is_stale_rectification(wrong_total) is True
    reason = raised(
        app_pool,
        cast.alicia,
        "select app.issue_rectifying_invoice(%s, 'a', 80000, %s, %s)",
        (original, D2, Jsonb(VALID_TERMS)),
    )
    assert repository.is_stale_rectification(reason) is False  # `terms` / `reason` no son «lo vigente cambió»


def test_payment_errors(app_pool: Pool, cast: Cast, r: Ready) -> None:
    p = problem(raised(app_pool, cast.alicia, "select app.set_invoice_paid(%s, true)", (uuid.uuid4(),)))
    assert (p.status, p.code) == (404, "invoice_not_found")
    original = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    with user_transaction(app_pool, cast.alicia.id) as conn:
        row = conn.execute(
            "select app.issue_rectifying_invoice(%s, 'Motivo', 80000, %s, %s) as id",
            (original, D2, Jsonb(rectification_terms(STANDING, 80_000))),
        ).fetchone()
    assert row is not None
    p = problem(raised(app_pool, cast.alicia, "select app.set_invoice_paid(%s, true)", (row["id"],)))
    assert (p.status, p.code) == (409, "invoice_not_payable")


def test_what_is_not_ours_is_not_translated(admin: Connection[DictRow], cast: Cast) -> None:
    with pytest.raises(psycopg.errors.UniqueViolation) as info:
        admin.execute("insert into public.profiles (id, email) values (%s, %s)", (uuid.uuid4(), cast.alicia.email))
    assert repository.translate_db_error(info.value) is None
    other = psycopg.errors.RaiseException("algo_inesperado")
    assert repository.translate_db_error(other) is None
