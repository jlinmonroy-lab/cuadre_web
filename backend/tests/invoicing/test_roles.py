"""AC-19 · Solo el rol `usuario` usa las facturas por la API; cada persona ve y toca lo suyo (SPEC-W-007 T7-05).

El gestor con vínculo activo lee las facturas por RLS (SPEC-W-010 le pondrá pantalla), pero la API de facturas es solo del `usuario`.
"""

from typing import Any

import pytest

from tests.invoicing.conftest import Api, invoice_body, rectification_body
from tests.support import Pool, apply_scenario

ZERO = "00000000-0000-4000-8000-000000000000"
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", "/api/invoices/preview", {}),
    ("POST", "/api/invoices", {}),
    ("POST", f"/api/invoices/{ZERO}/rectifications", rectification_body()),
    ("GET", "/api/invoices", None),
    ("GET", f"/api/invoices/{ZERO}", None),
    ("PUT", f"/api/invoices/{ZERO}/payment", {"paid": True}),
    ("GET", "/api/clients/billing", None),
]


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
@pytest.mark.parametrize(("method", "url", "body"), ROUTES)
def test_managers_and_admins_get_403(api: Api, who: str, method: str, url: str, body: dict[str, Any] | None) -> None:
    kwargs = {} if body is None else {"json": body}
    response = api.request(method, url, api.cast[who], **kwargs)
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize(("method", "url", "body"), ROUTES)
def test_every_route_needs_a_session(api: Api, method: str, url: str, body: dict[str, Any] | None) -> None:
    kwargs = {} if body is None else {"json": body}
    assert api.client.request(method, url, **kwargs).status_code == 401


def test_a_manager_with_an_active_link_cannot_issue_or_read_through_the_api(api: Api, app_pool: Pool) -> None:
    invoice = api.made(api.cast.alicia)
    apply_scenario(app_pool, api.cast, "active")
    assert api.get(api.cast.gina, invoice["id"]).status_code == 403
    assert api.request("GET", "/api/invoices", api.cast.gina).status_code == 403
    assert api.issue(api.cast.gina, invoice_body(api.cid())).status_code == 403


def test_a_suspended_account_gets_403(api: Api) -> None:
    api.admin.execute("update public.profiles set status = 'suspended' where id = %s", (api.cast.alicia.id,))
    assert api.issue(api.cast.alicia, invoice_body(api.cid())).status_code == 403
    assert api.request("GET", "/api/invoices", api.cast.alicia).status_code == 403


def test_a_manager_issues_nothing_even_with_a_valid_body(api: Api) -> None:
    api.issue(api.cast.gina, invoice_body(api.cid()))
    row = api.admin.execute("select count(*) as n from public.invoices").fetchone()
    mine = api.admin.execute(
        "select count(*) as n from public.invoices where owner_id = %s", (api.cast.gina.id,)
    ).fetchone()
    assert row is not None and mine == {"n": 0}


def test_nobody_reads_or_touches_anothers_invoices(api: Api) -> None:
    mine = api.made(api.cast.alicia)
    assert api.listing(api.cast.beto, year=2026) == []
    assert api.get(api.cast.beto, mine["id"]).status_code == 404
    assert api.pay(api.cast.beto, mine["id"], True).status_code == 404
    assert api.rectify(api.cast.beto, mine["id"]).status_code == 404
    assert api.get(api.cast.alicia, mine["id"]).json() == mine


def test_anothers_invoice_looks_exactly_like_one_that_does_not_exist(api: Api) -> None:
    mine = api.made(api.cast.alicia)
    foreign = api.get(api.cast.beto, mine["id"])
    missing = api.get(api.cast.beto, ZERO)

    def strip(r: Any) -> dict[str, Any]:
        return {k: v for k, v in r.json().items() if k != "request_id"}

    assert (foreign.status_code, strip(foreign)) == (missing.status_code, strip(missing))


def test_there_is_no_way_to_edit_or_delete_an_invoice(api: Api) -> None:
    """RES-03, T7-02: la API no ofrece PUT ni DELETE de facturas (solo cobrar y rectificar)."""
    mine = api.made(api.cast.alicia)
    for method in ("PUT", "PATCH", "DELETE"):
        response = api.request(method, f"/api/invoices/{mine['id']}", api.cast.alicia, json={})
        assert response.status_code in {404, 405}, method
    assert api.get(api.cast.alicia, mine["id"]).json() == mine
