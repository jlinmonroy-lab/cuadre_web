"""AC-04, AC-05, AC-06, AC-24 · Aceptar, rechazar y revocar por la API, y quién puede cada cosa (SPEC-W-010 hito 1)."""

import uuid

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.support import Pool, attempt


def gina_reads_alicia(pool: Pool, api: Api) -> bool:
    out = attempt(
        pool, api.cast.gina, "select owner_id from public.business_profiles where owner_id = %s", (api.cast.alicia.id,)
    )
    assert not out.error, out.message
    return bool(out.rows)


def code(response: object) -> str:
    return response.json()["code"]  # type: ignore[attr-defined,no-any-return]


# --- Invitaciones recibidas, aceptar y rechazar -----------------------------------------------------------------------------------------


def test_a_gestor_sees_the_pending_invitations_addressed_to_them_with_the_inviters_name(api: Api) -> None:
    mine = api.invited(api.cast.alicia, api.cast.gina.email)
    api.invited(api.cast.beto, api.cast.gus.email)  # de otro gestor
    response = api.invitations(api.cast.gina)
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    [row] = response.json()
    assert (row["id"], row["owner_name"]) == (mine, "Alicia") and set(row) == {
        "id",
        "owner_name",
        "invited_at",
        "expires_at",
    }
    assert api.invitations(api.cast.gus).json()[0]["owner_name"] == "Beto"


def test_accepting_opens_the_access_and_the_invitation_leaves_the_list(api: Api, app_pool: Pool) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    assert not gina_reads_alicia(app_pool, api)  # pendiente: ningún acceso
    response = api.accept(api.cast.gina, link)
    assert response.status_code == 204 and response.content == b""
    assert response.headers["cache-control"] == "private, no-store"
    assert gina_reads_alicia(app_pool, api)
    assert api.invitations(api.cast.gina).json() == []
    assert [(r["id"], r["status"]) for r in api.accesses(api.cast.alicia).json()] == [(link, "active")]


def test_declining_closes_the_invitation_without_any_access(api: Api, app_pool: Pool) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    assert api.decline(api.cast.gina, link).status_code == 204
    assert not gina_reads_alicia(app_pool, api)
    assert [r["status"] for r in api.accesses(api.cast.alicia).json()] == ["declined"]
    assert api.invitations(api.cast.gina).json() == []


def test_an_answered_invitation_cannot_be_answered_again(api: Api) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    assert api.accept(api.cast.gina, link).status_code == 204
    for answer in (api.accept, api.decline):
        response = answer(api.cast.gina, link)
        assert (response.status_code, code(response)) == (409, "gestor_access_not_pending")


def test_an_expired_invitation_cannot_be_accepted(api: Api, admin: Connection[DictRow]) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    admin.execute("update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (link,))
    response = api.accept(api.cast.gina, link)
    assert (response.status_code, code(response)) == (409, "gestor_access_expired")
    assert api.invitations(api.cast.gina).json() == []  # tampoco se ofrece


def test_an_invitation_addressed_to_somebody_else_is_not_found_for_everyone_else(api: Api) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    for answer in (api.accept, api.decline):
        response = answer(api.cast.gus, link)
        assert (response.status_code, code(response)) == (404, "gestor_access_not_found")
    assert [r["status"] for r in api.accesses(api.cast.alicia).json()] == ["pending"]


def test_an_unknown_id_is_not_found(api: Api) -> None:
    ghost = uuid.uuid4()
    assert (api.accept(api.cast.gina, ghost).status_code, api.revoke(api.cast.alicia, ghost).status_code) == (404, 404)


def test_an_id_that_is_not_a_uuid_is_a_validation_error(api: Api) -> None:
    response = api.revoke(api.cast.alicia, "no-es-un-uuid")
    assert (response.status_code, code(response)) == (422, "validation_error")


# --- Revocar ----------------------------------------------------------------------------------------------------------------------------


def test_revoking_cuts_the_access_at_once_and_the_gestor_loses_the_client(api: Api, app_pool: Pool) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    api.accept(api.cast.gina, link)
    assert gina_reads_alicia(app_pool, api)
    response = api.revoke(api.cast.alicia, link)
    assert response.status_code == 204 and response.headers["cache-control"] == "private, no-store"
    assert not gina_reads_alicia(app_pool, api), "tras revocar, la petición siguiente del gestor ya no lee nada"
    assert [r["status"] for r in api.accesses(api.cast.alicia).json()] == ["revoked"]


def test_revoking_also_withdraws_a_pending_invitation(api: Api) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    assert api.revoke(api.cast.alicia, link).status_code == 204
    assert api.invitations(api.cast.gina).json() == []
    response = api.accept(api.cast.gina, link)
    assert (response.status_code, code(response)) == (409, "gestor_access_not_pending")


def test_a_closed_access_cannot_be_revoked_again(api: Api) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    api.revoke(api.cast.alicia, link)
    response = api.revoke(api.cast.alicia, link)
    assert (response.status_code, code(response)) == (409, "gestor_access_not_open")


@pytest.mark.parametrize("who", ["beto", "gina", "gus", "adan"])
def test_only_the_owner_revokes_and_everybody_else_gets_not_found(api: Api, who: str) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    api.accept(api.cast.gina, link)
    response = api.revoke(api.cast[who], link)
    # Un autónomo ajeno y el gestor invitado reciben «no encontrado» (o `403` si su rol no puede usar la ruta): nunca un cambio.
    assert response.status_code in (403, 404)
    assert [r["status"] for r in api.accesses(api.cast.alicia).json()] == ["active"]


def test_the_log_keeps_the_whole_trail_in_order(api: Api, admin: Connection[DictRow]) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    api.accept(api.cast.gina, link)
    api.revoke(api.cast.alicia, link)
    rows = admin.execute(
        "select action, actor_role::text as role from public.activity_log where owner_id = %s and category = 'access' order by id",
        (api.cast.alicia.id,),
    ).fetchall()
    assert rows == [
        {"action": "gestor_access.invited", "role": "usuario"},
        {"action": "gestor_access.accepted", "role": "gestor"},
        {"action": "gestor_access.revoked", "role": "usuario"},
    ]


# --- Quién puede cada ruta ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_only_a_usuario_uses_the_owner_routes(api: Api, who: str) -> None:
    ghost = uuid.uuid4()
    for response in (
        api.invite(api.cast[who], "x@example.test"),
        api.accesses(api.cast[who]),
        api.revoke(api.cast[who], ghost),
    ):
        assert (response.status_code, code(response)) == (403, "forbidden")


@pytest.mark.parametrize("who", ["alicia", "beto", "adan"])
def test_only_a_gestor_uses_the_gestor_routes(api: Api, who: str) -> None:
    ghost = uuid.uuid4()
    for response in (
        api.invitations(api.cast[who]),
        api.accept(api.cast[who], ghost),
        api.decline(api.cast[who], ghost),
    ):
        assert (response.status_code, code(response)) == (403, "forbidden")


def test_without_a_session_every_route_is_401(api: Api) -> None:
    ghost = uuid.uuid4()
    for response in (
        api.invite(None, "x@example.test"),
        api.accesses(None),
        api.revoke(None, ghost),
        api.invitations(None),
        api.accept(None, ghost),
        api.decline(None, ghost),
    ):
        assert (response.status_code, code(response)) == (401, "unauthenticated")


def test_a_suspended_account_is_refused(api: Api, admin: Connection[DictRow]) -> None:
    admin.execute(
        "update public.profiles set status = 'suspended' where id = any(%s)", ([api.cast.alicia.id, api.cast.gina.id],)
    )
    assert api.invite(api.cast.alicia, "x@example.test").status_code == 403
    assert api.invitations(api.cast.gina).status_code == 403
