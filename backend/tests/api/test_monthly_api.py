"""AC-16 y AC-17 · La contabilidad mensual por la API (SPEC-W-012 §5.3, D-02, D-03, D-08), con la aplicación REAL y la base de datos real.

Septiembre de 2026 queda cerrado por el job de verdad; octubre (terminado, sin cierre) y noviembre (en curso) se calculan en vivo. El reloj de la API es fijo.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.auth import JwksTokenVerifier
from cuadre.jobs.closing_job import run_monthly_closing
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.clocks import FixedClock
from tests.jobs.closing_support import SHIFTS, apply_shift
from tests.jobs.test_cierre_mensual_job import bill, spend
from tests.rls.invoices_support import Ready, ready, series
from tests.support import Cast, Person, Pool

TODAY = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer

    def get(self, person: Person | None, path: str = "/api/monthly-closings", **params: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.signer.token(person)}"} if person is not None else {}
        return self.client.get(path, headers=headers, params=params)

    def year(self, person: Person | None, year: int | None = None) -> httpx.Response:
        return self.get(person, **({} if year is None else {"year": year}))

    def month(self, person: Person | None, year: int, month: int) -> httpx.Response:
        return self.get(person, f"/api/monthly-closings/{year}/{month}")


@pytest.fixture
def api(jwks_client: FakeJwksClient, signer: Signer) -> Iterator[Api]:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.state.clock = FixedClock(TODAY)
    with TestClient(application, raise_server_exceptions=False) as client:
        yield Api(application, client, signer)


def close_september(service_pool: Pool, app_pool: Pool, person: Person) -> None:
    run_monthly_closing(
        service_pool=service_pool,
        app_pool=app_pool,
        now=datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
        only_owners=[person.id],
    )


def story(admin: Connection[DictRow], app_pool: Pool, service_pool: Pool, person: Person) -> Ready:
    """Septiembre cerrado (nacional + UE + un gasto), octubre con una factura sin cerrar y noviembre en curso."""
    r = ready(admin, person)
    bill(app_pool, admin, person, r, "national", date(2026, 9, 3), 150_000)
    bill(app_pool, admin, person, r, "eu", date(2026, 9, 10), 50_000)
    spend(admin, app_pool, person, date(2026, 9, 5))
    close_september(service_pool, app_pool, person)
    bill(app_pool, admin, person, r, "national", date(2026, 10, 5), 20_000)
    bill(app_pool, admin, person, r, "non_eu", date(2026, 11, 4), 7_000)
    spend(admin, app_pool, person, date(2026, 11, 3))
    return r


# --- AC-16 · La lista del año -------------------------------------------------------------------------------------------------------------


def test_the_year_shows_closed_pending_and_in_progress_months(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    response = api.year(cast.alicia)
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert body["year"] == 2026
    sep, oct_, nov = body["months"]
    assert [m["month"] for m in (sep, oct_, nov)] == [9, 10, 11]
    assert [m["status"] for m in (sep, oct_, nov)] == ["closed", "pending", "in_progress"]

    assert (
        sep["invoice_count"],
        sep["national_cents"],
        sep["eu_cents"],
        sep["total_cents"],
        sep["expenses_cents"],
    ) == (
        2,
        150_000,
        50_000,
        200_000,
        10_000,
    )
    assert sep["revision"] == 1 and sep["closed_at"] is not None
    assert [m["result_cents"] for m in (sep, oct_, nov)] == [
        190_000,
        20_000,
        -3_000,
    ]  # ingresos menos gastos, con signo
    assert (oct_["total_cents"], oct_["national_cents"], oct_["invoice_count"]) == (20_000, 20_000, 1)
    assert (nov["total_cents"], nov["non_eu_cents"], nov["expenses_cents"]) == (7_000, 7_000, 10_000)
    assert (
        oct_["revision"] is None and oct_["closed_at"] is None and nov["revision"] is None
    )  # solo los cerrados llevan revisión

    assert [m["ytd_cents"] for m in (sep, oct_, nov)] == [200_000, 220_000, 227_000]  # derivado, nunca guardado
    assert body["totals"] == {
        "invoice_count": 4,
        "national_cents": 170_000,
        "eu_cents": 50_000,
        "non_eu_cents": 7_000,
        "total_cents": 227_000,
        "expenses_cents": 20_000,
    }


def test_the_live_figures_equal_what_the_job_will_close(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    before = api.month(cast.alicia, 2026, 10).json()
    assert before["status"] == "pending"
    run_monthly_closing(service_pool=service_pool, app_pool=app_pool, now=TODAY, only_owners=[cast.alicia.id])
    after = api.month(cast.alicia, 2026, 10).json()
    assert after["status"] == "closed" and after["revision"] == 1
    for key in (
        "invoice_count",
        "national_cents",
        "eu_cents",
        "non_eu_cents",
        "total_cents",
        "expenses_cents",
        "ytd_cents",
        "by_client",
    ):
        assert after[key] == before[key], key
    assert api.month(cast.alicia, 2026, 11).json()["status"] == "in_progress"  # el mes en curso nunca se cierra


@pytest.mark.parametrize("shift", SHIFTS)
def test_a_new_account_sees_its_first_month_in_progress(
    api: Api, admin: Connection[DictRow], cast: Cast, shift: datetime | None
) -> None:
    signup = apply_shift(admin, cast.alicia, shift)
    api.app.state.clock = FixedClock(
        datetime(signup.year, signup.month, 15, 8, 0, tzinfo=UTC)
    )  # el mes de alta es el mes en curso
    body = api.year(cast.alicia).json()
    assert body["year"] == signup.year
    assert [(m["month"], m["status"], m["total_cents"], m["ytd_cents"]) for m in body["months"]] == [
        (signup.month, "in_progress", 0, 0)
    ]
    assert body["totals"]["total_cents"] == 0


def test_a_year_before_the_first_activity_is_empty(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    body = api.year(cast.alicia, 2025).json()
    assert body["year"] == 2025 and body["months"] == []
    assert set(body["totals"].values()) == {0}


def test_the_months_before_the_first_one_with_activity_are_not_listed(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    assert [m["month"] for m in api.year(cast.alicia, 2026).json()["months"]][
        0
    ] == 9  # la primera factura es de septiembre


def test_a_late_document_shows_up_only_after_the_next_run_of_the_job(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = story(admin, app_pool, service_pool, cast.alicia)
    before = api.month(cast.alicia, 2026, 9).json()
    spend(admin, app_pool, cast.alicia, date(2026, 9, 28))
    other = series(admin, cast.alicia, "TARDE")
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 9, 14), 5_000, series_id=other)

    assert api.month(cast.alicia, 2026, 9).json() == before  # la foto no se refresca al leer

    run_monthly_closing(service_pool=service_pool, app_pool=app_pool, now=TODAY, only_owners=[cast.alicia.id])
    after = api.month(cast.alicia, 2026, 9).json()
    assert (after["revision"], after["total_cents"], after["expenses_cents"]) == (2, 205_000, 20_000)
    ytd = [m["ytd_cents"] for m in api.year(cast.alicia).json()["months"]]
    assert ytd == [205_000, 225_000, 232_000]  # el acumulado de los meses siguientes recoge el cambio


def test_a_closing_that_exists_is_listed_even_if_its_month_is_no_longer_the_first_with_activity(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """Si el único documento que fijaba el primer mes se anula después, el cierre que ya se guardó sigue saliendo en la lista."""
    expense = spend(admin, app_pool, cast.alicia, date(2026, 8, 12))
    run_monthly_closing(
        service_pool=service_pool,
        app_pool=app_pool,
        now=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        only_owners=[cast.alicia.id],
    )
    admin.execute("update public.expenses set voided_at = now() where id = %s", (expense,))
    body = api.year(cast.alicia).json()
    assert [(m["month"], m["status"]) for m in body["months"]][0] == (8, "closed")  # agosto sigue ahí, con su foto
    assert api.month(cast.alicia, 2026, 8).json()["expenses_cents"] == 10_000


@pytest.mark.parametrize("shift", SHIFTS)
def test_one_person_never_sees_the_figures_of_another(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, shift: datetime | None
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    signup = apply_shift(admin, cast.beto, shift)
    api.app.state.clock = FixedClock(datetime(signup.year, signup.month, 15, 8, 0, tzinfo=UTC))
    body = api.year(cast.beto).json()
    assert [(m["month"], m["total_cents"]) for m in body["months"]] == [(signup.month, 0)]  # nada de lo de Alicia
    assert api.month(cast.beto, 2026, 9).status_code == 404


@pytest.mark.parametrize(
    ("year", "code"),
    [(2027, "period_in_future"), (9998, "period_in_future"), (1999, "invalid_period"), (10000, "invalid_period")],
)
def test_a_year_that_does_not_exist_or_has_not_started_is_refused(api: Api, cast: Cast, year: int, code: str) -> None:
    response = api.year(cast.alicia, year)
    assert response.status_code == 422 and response.json()["code"] == code
    assert response.headers["content-type"].startswith("application/problem+json")


def test_a_year_that_is_not_a_number_is_a_validation_error(api: Api, cast: Cast) -> None:
    response = api.get(cast.alicia, year="dos mil")
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


# --- AC-17 · El detalle de un mes ---------------------------------------------------------------------------------------------------------


def test_a_closed_month_has_its_clients_ordered_and_the_same_ytd_as_the_list(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = story(admin, app_pool, service_pool, cast.alicia)
    detail = api.month(cast.alicia, 2026, 9).json()
    assert detail["year"] == 2026 and detail["status"] == "closed" and detail["revision"] == 1
    assert [(c["scope"], c["base_cents"], c["invoice_count"]) for c in detail["by_client"]] == [
        ("national", 150_000, 1),
        ("eu", 50_000, 1),
    ]
    assert {c["client_id"] for c in detail["by_client"]} == {
        str(r.clients[("national", "business")]),
        str(r.clients[("eu", "business")]),
    }
    assert all(set(c) == {"client_id", "name", "scope", "base_cents", "invoice_count"} for c in detail["by_client"])
    listed = {m["month"]: m for m in api.year(cast.alicia).json()["months"]}
    assert detail["ytd_cents"] == listed[9]["ytd_cents"] and detail["total_cents"] == listed[9]["total_cents"]
    for month in (10, 11):
        assert api.month(cast.alicia, 2026, month).json()["ytd_cents"] == listed[month]["ytd_cents"]


def test_the_month_in_progress_and_a_pending_one_are_calculated_live(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    nov = api.month(cast.alicia, 2026, 11).json()
    assert (nov["status"], nov["total_cents"], nov["revision"], nov["closed_at"]) == ("in_progress", 7_000, None, None)
    assert [(c["scope"], c["base_cents"]) for c in nov["by_client"]] == [("non_eu", 7_000)]
    assert api.month(cast.alicia, 2026, 10).json()["status"] == "pending"


@pytest.mark.parametrize(
    ("year", "month", "status", "code"),
    [
        (2026, 12, 422, "period_in_future"),
        (2027, 1, 422, "period_in_future"),
        (2026, 0, 422, "invalid_period"),
        (2026, 13, 422, "invalid_period"),
        (1999, 5, 422, "invalid_period"),
    ],
)
def test_a_month_that_does_not_exist_or_has_not_started_is_refused(
    api: Api, cast: Cast, year: int, month: int, status: int, code: str
) -> None:
    response = api.month(cast.alicia, year, month)
    assert response.status_code == status and response.json()["code"] == code


def test_a_month_before_the_first_one_with_activity_is_not_found(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    for year, month in ((2026, 8), (2026, 1), (2025, 12)):
        response = api.month(cast.alicia, year, month)
        assert response.status_code == 404 and response.json()["code"] == "closing_not_found"


# --- Acceso y contrato --------------------------------------------------------------------------------------------------------------------


def test_without_a_session_the_answer_is_401(api: Api) -> None:
    assert api.year(None).status_code == 401 and api.month(None, 2026, 9).status_code == 401


@pytest.mark.parametrize("who", ["gina", "adan"])
def test_gestores_and_admins_cannot_use_it(api: Api, cast: Cast, who: str) -> None:
    assert api.year(cast[who]).status_code == 403
    assert api.month(cast[who], 2026, 9).status_code == 403


def test_a_suspended_account_cannot_use_it(api: Api, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert api.year(cast.alicia).status_code == 403 and api.month(cast.alicia, 2026, 11).status_code == 403


def test_both_routes_are_in_the_public_contract(api: Api) -> None:
    paths = api.app.openapi()["paths"]
    assert paths["/api/monthly-closings"]["get"]["operationId"] == "get_monthly_closings"
    assert paths["/api/monthly-closings/{year}/{month}"]["get"]["operationId"] == "get_monthly_closing"
