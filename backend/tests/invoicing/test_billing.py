"""AC-23 · Lo facturado por cliente (SPEC-W-007 §5.3): suma de bases con signo, por año de expedición. Una lectura no escribe."""

from typing import Any

import pytest

from tests.invoicing.conftest import Api
from tests.rls.invoices_support import client


def as_map(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {r["client_id"]: r["billed_cents"] for r in rows}


def billed(api: Api, person: Any = None, **params: Any) -> dict[str, int]:
    response = api.billing(person or api.cast.alicia, **params)
    assert response.status_code == 200, response.text
    return as_map(response.json())


def test_the_route_is_not_taken_for_a_client_id(api: Api) -> None:
    """`/api/clients/billing` va antes que `/api/clients/{client_id}`: si no, «billing» daría un 422 de uuid."""
    response = api.billing(api.cast.alicia, year=2026)
    assert response.status_code == 200 and isinstance(response.json(), list)
    assert api.request("GET", "/api/clients/no-uuid", api.cast.alicia).status_code == 422


def test_it_sums_the_bases_of_each_client(api: Api) -> None:
    api.made(api.cast.alicia, "national", "business", base_cents=100_000)
    api.made(api.cast.alicia, "national", "business", base_cents=50_000)
    api.made(api.cast.alicia, "eu", "business", base_cents=70_000)
    assert billed(api, year=2026) == {str(api.cid()): 150_000, str(api.cid("eu", "business")): 70_000}


def test_the_rectifications_subtract_in_the_year_of_their_own_date(api: Api) -> None:
    original = api.made(api.cast.alicia, issue_date="2025-12-20")
    api.rectify(api.cast.alicia, original["id"], issue_date="2026-01-05", corrected_base_cents=60_000)
    assert billed(api, year=2025) == {str(api.cid()): 100_000}
    assert billed(api, year=2026) == {str(api.cid()): -40_000}


def test_the_first_and_last_day_of_the_year_belong_to_that_year(api: Api) -> None:
    api.made(api.cast.alicia, issue_date="2025-12-31", base_cents=1_000)
    api.made(api.cast.alicia, issue_date="2026-01-01", base_cents=20_000)
    assert billed(api, year=2025) == {str(api.cid()): 1_000}
    assert billed(api, year=2026) == {str(api.cid()): 20_000}


def test_a_full_cancellation_in_the_same_year_nets_to_zero(api: Api) -> None:
    original = api.made(api.cast.alicia)
    api.rectify(api.cast.alicia, original["id"], corrected_base_cents=0)
    assert billed(api, year=2026) == {str(api.cid()): 0}


def test_an_archived_client_still_shows_what_was_billed(api: Api) -> None:
    api.made(api.cast.alicia)
    api.admin.execute("update public.clients set archived_at = now() where id = %s", (api.cid(),))
    assert billed(api, year=2026) == {str(api.cid()): 100_000}


def test_clients_without_invoices_and_other_years_do_not_appear(api: Api) -> None:
    api.made(api.cast.alicia, issue_date="2025-06-01")
    assert billed(api, year=2026) == {}
    assert billed(api, year=2025) == {str(api.cid()): 100_000}
    other = client(api.admin, api.cast.alicia)
    assert str(other) not in billed(api, year=2025)


def test_the_default_year_is_the_current_one(api: Api) -> None:
    api.made(api.cast.alicia, issue_date=api.today().isoformat())
    assert billed(api) == {str(api.cid()): 100_000}


def test_each_person_sees_only_their_own(api: Api) -> None:
    api.made(api.cast.alicia)
    assert billed(api, api.cast.beto, year=2026) == {}


@pytest.mark.parametrize("year", ["1999", "9999", "abc"])
def test_a_bad_year_is_a_validation_error(api: Api, year: str) -> None:
    response = api.billing(api.cast.alicia, year=year)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
