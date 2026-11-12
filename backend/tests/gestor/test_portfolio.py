"""AC-07, AC-08 · La cartera del gestor: sus autónomos con acceso activo y los pendientes de cada uno (SPEC-W-010 hito 2, US-010)."""

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.gestor.support import documents, link, reads
from tests.support import Pool, apply_scenario, invite, make_cast

URL = "/api/gestor/cartera"


def entries(api: Api, gestor: object) -> list[dict[str, object]]:
    response = api.request("GET", URL, gestor)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()  # type: ignore[no-any-return]


def test_the_portfolio_lists_the_three_clients_and_marks_the_one_with_four_pending(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:  # AC-07, US-010
    cast = api.cast
    carla = make_cast(admin).alicia  # una tercera autónoma, de otro reparto
    for owner in (cast.alicia, cast.beto, carla):
        link(app_pool, owner, cast.gina)
    documents(app_pool, cast.alicia, "review", 4)
    rows = entries(api, cast.gina)
    assert {r["id"] for r in rows} == {str(cast.alicia.id), str(cast.beto.id), str(carla.id)}
    pending = {r["id"]: r["pending_count"] for r in rows}
    assert pending == {str(cast.alicia.id): 4, str(cast.beto.id): 0, str(carla.id): 0}
    assert rows[0]["id"] == str(cast.alicia.id), "el que tiene pendientes sale primero"
    assert set(rows[0]) == {"id", "name", "email", "pending_count"}
    assert (rows[0]["name"], rows[0]["email"]) == ("Alicia", cast.alicia.email)


def test_only_documents_in_review_count_as_pending(api: Api, app_pool: Pool) -> None:
    cast = api.cast
    link(app_pool, cast.alicia, cast.gina)
    documents(app_pool, cast.alicia, "review", 2)
    for state in ("processing", "extraction_failed", "discarded", "registered", "uploading"):
        documents(app_pool, cast.alicia, state, 1)
    assert [r["pending_count"] for r in entries(api, cast.gina)] == [2]


def test_without_pending_documents_there_is_no_mark_and_the_order_is_by_name(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    cast = api.cast
    other = make_cast(admin).alicia
    link(app_pool, cast.beto, cast.gina)  # «Beto»
    link(app_pool, other, cast.gina)  # «Alicia»
    rows = entries(api, cast.gina)
    assert [r["name"] for r in rows] == ["Alicia", "Beto"] and [r["pending_count"] for r in rows] == [0, 0]


def test_only_active_links_with_this_gestor_appear(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:  # AC-08
    cast = api.cast
    pending, declined, revoked, active, expired = (make_cast(admin).alicia for _ in range(5))
    invite(app_pool, pending, cast.gina)  # pendiente
    declined_link = invite(app_pool, declined, cast.gina)
    assert api.decline(cast.gina, declined_link).status_code == 204
    revoked_link = link(app_pool, revoked, cast.gina)
    assert api.revoke(revoked, revoked_link).status_code == 204
    link(app_pool, active, cast.gina)
    expired_link = invite(app_pool, expired, cast.gina)
    admin.execute(
        "update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (expired_link,)
    )
    other = link(app_pool, cast.beto, cast.gus)  # de OTRO gestor
    assert other
    assert [r["id"] for r in entries(api, cast.gina)] == [str(active.id)]
    assert [r["id"] for r in entries(api, cast.gus)] == [str(cast.beto.id)]


def test_a_pending_link_does_not_appear_even_if_it_already_names_the_gestor(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    """Una pendiente no entra en la cartera aunque ya nombre al gestor. Lo garantiza la RLS de `profiles` (sin vínculo activo no se lee el perfil), no el `status` de la consulta: la mutación de ese filtro es equivalente."""
    cast = api.cast
    pending_link = invite(app_pool, cast.alicia, cast.gina)
    admin.execute("update public.gestor_access set gestor_id = %s where id = %s", (cast.gina.id, pending_link))
    assert entries(api, cast.gina) == []


def test_a_gestor_without_clients_sees_an_empty_portfolio(api: Api) -> None:
    assert entries(api, api.cast.gus) == []


def test_after_revoking_the_client_leaves_the_portfolio_at_once(api: Api, app_pool: Pool) -> None:  # AC-05
    cast = api.cast
    access = link(app_pool, cast.alicia, cast.gina)
    assert [r["id"] for r in entries(api, cast.gina)] == [str(cast.alicia.id)]
    assert api.revoke(cast.alicia, access).status_code == 204
    assert entries(api, cast.gina) == []


def test_each_client_shown_is_logged_once_per_request_and_nobody_else(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    cast = api.cast
    link(app_pool, cast.alicia, cast.gina)
    link(app_pool, cast.beto, cast.gina)
    entries(api, cast.gina)
    entries(api, cast.gina)
    for owner in (cast.alicia, cast.beto):
        rows = reads(admin, owner)
        assert [(r["entity_type"], r["actor_id"], r["actor_role"]) for r in rows] == [
            ("portfolio", cast.gina.id, "gestor")
        ] * 2
    assert reads(admin, cast.gus) == []


def test_only_a_gestor_opens_the_portfolio(api: Api) -> None:
    for who in ("alicia", "beto", "adan"):
        response = api.request("GET", URL, api.cast[who])
        assert (response.status_code, response.json()["code"]) == (403, "forbidden"), who
    assert api.request("GET", URL, None).status_code == 401


@pytest.mark.parametrize(
    ("scenario", "expected"), [("baseline", 0), ("pending", 0), ("declined", 0), ("revoked", 0), ("active", 1)]
)
def test_the_scenarios_of_the_matrix_agree_with_the_portfolio(
    api: Api, app_pool: Pool, scenario: str, expected: int
) -> None:
    apply_scenario(app_pool, api.cast, scenario)
    assert len(entries(api, api.cast.gina)) == expected
