"""AC-12 · Solo el rol `usuario` usa los clientes; cada persona ve y toca lo suyo (SPEC-W-006 T6-03)."""

from typing import Any

import pytest

from tests.clients.conftest import BODY, Api

ZERO = "00000000-0000-4000-8000-000000000000"
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/clients", None),
    ("POST", "/api/clients", BODY),
    ("GET", f"/api/clients/{ZERO}", None),
    ("PUT", f"/api/clients/{ZERO}", BODY),
    ("PUT", f"/api/clients/{ZERO}/archived", {"archived": True}),
]


@pytest.mark.parametrize("who", ["gina", "adan"])
@pytest.mark.parametrize(("method", "url", "body"), ROUTES)
def test_ac12_managers_and_admins_get_403(
    api: Api, who: str, method: str, url: str, body: dict[str, Any] | None
) -> None:
    kwargs = {} if body is None else {"json": body}
    response = api.request(method, url, api.cast[who], **kwargs)
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize(("method", "url", "body"), ROUTES)
def test_every_route_needs_a_session(api: Api, method: str, url: str, body: dict[str, Any] | None) -> None:
    kwargs = {} if body is None else {"json": body}
    assert api.client.request(method, url, **kwargs).status_code == 401


def test_a_manager_cannot_create_a_client_even_with_a_valid_body(api: Api, admin: Any) -> None:
    api.request("POST", "/api/clients", api.cast.gina, json=BODY)
    assert (
        admin.execute("select count(*) as n from public.clients where owner_id = %s", (api.cast.gina.id,)).fetchone()[
            "n"
        ]
        == 0
    )


def test_ac12_nobody_reads_or_touches_anothers_clients(api: Api) -> None:
    mine = api.made(api.cast.alicia)
    assert api.listing(api.cast.beto, archived=True) == []
    assert api.get(api.cast.beto, mine["id"]).status_code == 404
    assert api.update(api.cast.beto, mine["id"], name="Hackeado S.L.").status_code == 404
    assert api.archive(api.cast.beto, mine["id"], True).status_code == 404
    assert api.get(api.cast.alicia, mine["id"]).json() == mine


def test_anothers_client_looks_exactly_like_one_that_does_not_exist(api: Api) -> None:
    mine = api.made(api.cast.alicia)
    foreign = api.get(api.cast.beto, mine["id"])
    missing = api.get(api.cast.beto, ZERO)
    strip = lambda r: {k: v for k, v in r.json().items() if k != "request_id"}  # noqa: E731
    assert (foreign.status_code, strip(foreign)) == (missing.status_code, strip(missing))


def test_a_suspended_account_changes_nothing(api: Api, admin: Any) -> None:
    mine = api.made(api.cast.alicia)
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (api.cast.alicia.id,))
    assert api.create(api.cast.alicia, name="Otro S.L.", tax_id="B00000026").status_code == 403
    assert api.archive(api.cast.alicia, mine["id"], True).status_code == 403
    assert (
        admin.execute("select archived_at from public.clients where id = %s", (mine["id"],)).fetchone()["archived_at"]
        is None
    )
