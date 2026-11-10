"""AC-22 · El listado y lo facturado por cliente (SPEC-W-007 §5.3, T7-07): orden, año, filtros y signo. Una lectura no escribe."""

from typing import Any

import pytest

from tests.invoicing.conftest import Api
from tests.rls.invoices_support import D1, D2, D3


def numbers(rows: list[dict[str, Any]]) -> list[str]:
    return [r["display_number"] for r in rows]


def test_the_list_is_the_years_invoices_the_latest_first(api: Api) -> None:
    api.made(api.cast.alicia, issue_date=D1.isoformat())
    api.made(api.cast.alicia, issue_date=D2.isoformat())
    api.made(api.cast.alicia, issue_date=D3.isoformat())
    assert numbers(api.listing(api.cast.alicia, year=2026)) == ["2026-003", "2026-002", "2026-001"]


def test_two_invoices_of_the_same_day_are_listed_the_later_first(api: Api) -> None:
    api.made(api.cast.alicia, issue_date=D1.isoformat())
    api.made(api.cast.alicia, issue_date=D1.isoformat())
    assert numbers(api.listing(api.cast.alicia, year=2026)) == ["2026-002", "2026-001"]


def test_only_the_year_asked_is_listed_and_the_default_is_the_current_year(api: Api) -> None:
    api.made(api.cast.alicia, issue_date="2025-12-31")
    api.made(api.cast.alicia, issue_date="2026-01-01")
    assert numbers(api.listing(api.cast.alicia, year=2025)) == ["2026-001"]
    assert numbers(api.listing(api.cast.alicia, year=2026)) == ["2026-002"]
    assert api.listing(api.cast.alicia, year=2024) == []
    expected = ["2026-002"] if api.today().year == 2026 else []
    assert numbers(api.listing(api.cast.alicia)) == expected


def test_the_rectifications_are_listed_with_the_year_of_their_own_date(api: Api) -> None:
    original = api.made(api.cast.alicia, issue_date="2025-12-20")
    api.rectify(api.cast.alicia, original["id"], issue_date="2026-01-05")
    assert numbers(api.listing(api.cast.alicia, year=2025)) == ["2026-001"]
    assert numbers(api.listing(api.cast.alicia, year=2026)) == ["R-2026-001"]


def test_the_scope_filter(api: Api) -> None:
    api.made(api.cast.alicia, "national", "business")
    api.made(api.cast.alicia, "eu", "business")
    api.made(api.cast.alicia, "eu", "individual")
    api.made(api.cast.alicia, "non_eu", "business")
    scoped = {
        s: sorted(r["client"]["scope"] for r in api.listing(api.cast.alicia, year=2026, scope=s))
        for s in ("national", "eu", "non_eu")
    }
    assert scoped == {"national": ["national"], "eu": ["eu", "eu"], "non_eu": ["non_eu"]}
    assert len(api.listing(api.cast.alicia, year=2026)) == 4


def test_the_paid_filter_only_looks_at_ordinary_invoices(api: Api) -> None:
    paid = api.made(api.cast.alicia)
    pending = api.made(api.cast.alicia)
    api.pay(api.cast.alicia, paid["id"], True)
    api.rectify(api.cast.alicia, pending["id"])
    assert numbers(api.listing(api.cast.alicia, year=2026, paid="true")) == ["2026-001"]
    assert numbers(api.listing(api.cast.alicia, year=2026, paid="false")) == [
        "2026-002"
    ]  # la rectificativa no está «pendiente de cobro»
    assert len(api.listing(api.cast.alicia, year=2026)) == 3


@pytest.mark.parametrize(
    "params", [{"year": 1999}, {"year": 9999}, {"year": "abc"}, {"scope": "mars"}, {"paid": "maybe"}]
)
def test_bad_query_values_are_a_validation_error(api: Api, params: dict[str, Any]) -> None:
    response = api.request("GET", "/api/invoices", api.cast.alicia, params=params)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_each_person_lists_only_their_own(api: Api) -> None:
    api.made(api.cast.alicia)
    assert api.listing(api.cast.beto, year=2026) == []


def test_listing_and_reading_write_nothing(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    paid_at = api.pay(api.cast.alicia, invoice["id"], True).json()["paid_at"]
    before = api.admin.execute(
        "select count(*) as n from public.activity_log where owner_id = %s", (api.cast.alicia.id,)
    ).fetchone()
    series = api.admin.execute(
        "select next_number from public.invoice_series where id = %s", (api.world.series,)
    ).fetchone()
    api.listing(api.cast.alicia, year=2026)
    api.get(api.cast.alicia, invoice["id"])
    api.billing(api.cast.alicia, year=2026)
    after = api.admin.execute(
        "select count(*) as n from public.activity_log where owner_id = %s", (api.cast.alicia.id,)
    ).fetchone()
    assert after == before
    assert (
        api.admin.execute("select next_number from public.invoice_series where id = %s", (api.world.series,)).fetchone()
        == series
    )
    assert api.get(api.cast.alicia, invoice["id"]).json()["paid_at"] == paid_at  # leer no descobra ni vuelve a cobrar
