"""AC-09, AC-24 · `owner_scope`: sin vínculo vigente, la misma `404` para todo; con el rol equivocado, `403`; sin sesión, `401` (SPEC-W-010 hito 2)."""

import uuid
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.gestor.support import access_log, link
from tests.support import Pool, apply_scenario, invite

GHOST = uuid.UUID("00000000-0000-4000-8000-00000000abcd")


def routes(owner: object) -> list[tuple[str, str, dict[str, Any] | None]]:
    base = f"/api/gestor/autonomos/{owner}"
    return [
        ("GET", base, None),
        ("GET", f"{base}/facturas", None),
        ("GET", f"{base}/facturas/{GHOST}", None),
        ("GET", f"{base}/facturas/{GHOST}/pdf", None),
        ("GET", f"{base}/gastos", None),
        ("GET", f"{base}/documentos", None),
        ("GET", f"{base}/documentos/{GHOST}/original", None),
        ("GET", f"{base}/perfil", None),
        ("GET", f"{base}/clientes", None),
        ("GET", f"{base}/trimestres/303?year=2025&quarter=1", None),
        ("GET", f"{base}/trimestres/130?year=2025&quarter=1", None),
        ("GET", f"{base}/anotaciones", None),
        ("POST", f"{base}/anotaciones", {"body": "Hola"}),
    ]


def call(api: Api, person: object, method: str, url: str, body: dict[str, Any] | None) -> Any:
    kwargs: dict[str, Any] = {} if body is None else {"json": body}
    return api.request(method, url, person, **kwargs)  # type: ignore[arg-type]


def stable(response: Any) -> dict[str, Any]:
    """El cuerpo de un error sin lo que cambia en cada petición."""
    return {k: v for k, v in response.json().items() if k != "request_id"}


@pytest.mark.parametrize("scenario", ["baseline", "pending", "declined", "revoked"])
def test_without_a_vigent_link_every_route_answers_the_same_404(api: Api, app_pool: Pool, scenario: str) -> None:
    apply_scenario(app_pool, api.cast, scenario)
    bodies = []
    for method, url, body in routes(api.cast.alicia.id):
        response = call(api, api.cast.gina, method, url, body)
        assert response.status_code == 404, (scenario, method, url, response.text)
        assert response.headers["content-type"].startswith("application/problem+json")
        bodies.append(stable(response))
    assert all(b == bodies[0] for b in bodies) and bodies[0]["code"] == "not_found"


def test_the_404_is_identical_for_a_real_client_without_a_link_and_for_an_id_that_does_not_exist(api: Api) -> None:
    real = [stable(call(api, api.cast.gina, m, u, b)) for m, u, b in routes(api.cast.alicia.id)]
    ghost = [stable(call(api, api.cast.gina, m, u, b)) for m, u, b in routes(GHOST)]
    assert real == ghost


def test_a_gestor_cannot_read_themselves_or_a_client_of_another_gestor(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.beto, api.cast.gus)  # Beto es de Gus, no de Gina
    for owner in (api.cast.beto.id, api.cast.gina.id):
        for method, url, body in routes(owner):
            assert call(api, api.cast.gina, method, url, body).status_code == 404, (owner, url)


def test_an_active_link_with_one_client_gives_nothing_of_another(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    assert api.request("GET", f"/api/gestor/autonomos/{api.cast.alicia.id}", api.cast.gina).status_code == 200
    assert api.request("GET", f"/api/gestor/autonomos/{api.cast.beto.id}", api.cast.gina).status_code == 404


def test_an_expired_pending_invitation_gives_no_access(api: Api, app_pool: Pool, admin: Connection[DictRow]) -> None:
    pending = invite(app_pool, api.cast.alicia, api.cast.gina)
    admin.execute("update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (pending,))
    assert api.request("GET", f"/api/gestor/autonomos/{api.cast.alicia.id}", api.cast.gina).status_code == 404


def test_a_suspended_gestor_gets_nothing(api: Api, app_pool: Pool, admin: Connection[DictRow]) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (api.cast.gina.id,))
    assert api.request("GET", f"/api/gestor/autonomos/{api.cast.alicia.id}", api.cast.gina).status_code == 403


def test_the_role_decides_before_the_link(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    for who in ("alicia", "beto", "adan"):
        for method, url, body in routes(api.cast.alicia.id):
            response = call(api, api.cast[who], method, url, body)
            assert (response.status_code, response.json()["code"]) == (403, "forbidden"), (who, url)


def test_without_a_session_every_route_is_401(api: Api) -> None:
    for method, url, body in routes(api.cast.alicia.id):
        response = call(api, None, method, url, body)
        assert (response.status_code, response.json()["code"]) == (401, "unauthenticated"), url


def test_an_id_that_is_not_a_uuid_is_a_validation_error_not_a_404(api: Api) -> None:
    response = api.request("GET", "/api/gestor/autonomos/no-es-un-uuid/facturas", api.cast.gina)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


# --- AC-24 · revocar a mitad ----------------------------------------------------------------------------------------------------------


def test_after_revoking_nothing_more_is_read_and_nothing_stays_cached(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    access = link(app_pool, api.cast.alicia, api.cast.gina)
    owner = api.cast.alicia.id
    assert api.request("GET", f"/api/gestor/autonomos/{owner}/perfil", api.cast.gina).status_code == 200
    assert api.request("GET", f"/api/gestor/autonomos/{owner}/clientes", api.cast.gina).status_code == 200
    before = len(access_log(admin, api.cast.alicia))
    assert api.revoke(api.cast.alicia, access).status_code == 204
    after_revoking = len(access_log(admin, api.cast.alicia))
    for method, url, body in routes(owner):
        assert call(api, api.cast.gina, method, url, body).status_code == 404, url
    assert after_revoking == before + 1  # solo el rastro de la revocación: ninguna lectura posterior dejó nada
    assert len(access_log(admin, api.cast.alicia)) == after_revoking


def test_a_new_invitation_after_revoking_restores_reading_only_when_accepted(api: Api, app_pool: Pool) -> None:
    access = link(app_pool, api.cast.alicia, api.cast.gina)
    api.revoke(api.cast.alicia, access)
    owner = api.cast.alicia.id
    again = api.invited(api.cast.alicia, api.cast.gina.email)
    assert api.request("GET", f"/api/gestor/autonomos/{owner}", api.cast.gina).status_code == 404  # pendiente: nada
    assert api.accept(api.cast.gina, again).status_code == 204
    assert api.request("GET", f"/api/gestor/autonomos/{owner}", api.cast.gina).status_code == 200
