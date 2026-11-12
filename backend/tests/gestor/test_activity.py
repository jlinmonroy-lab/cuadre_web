"""AC-16 · El registro de actividad del autónomo: qué se hizo con el acceso de su gestor y qué leyó, paginado y sin datos financieros (SPEC-W-010 hito 2)."""

import json
import uuid
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.support import Pool

KEYS = {"id", "occurred_at", "action", "actor_role", "actor_email", "entity_type", "entity_id", "year", "quarter"}


def activity(api: Api, who: object, **params: Any) -> Any:
    return api.request("GET", "/api/gestor/actividad", who, params=params or None)  # type: ignore[arg-type]


def test_the_whole_trail_in_order_with_who_and_what_and_no_financial_data(api: Api, app_pool: Pool) -> None:
    cast = api.cast
    access = api.invited(cast.alicia, cast.gina.email)
    assert api.accept(cast.gina, access).status_code == 204
    base = f"/api/gestor/autonomos/{cast.alicia.id}"
    assert (
        api.request("GET", f"{base}/trimestres/130", cast.gina, params={"year": 2025, "quarter": 2}).status_code == 200
    )
    assert api.request("GET", f"{base}/clientes", cast.gina).status_code == 200
    note = api.request("POST", f"{base}/anotaciones", cast.gina, json={"body": "Texto reservado"}).json()
    assert api.revoke(cast.alicia, access).status_code == 204

    response = activity(api, cast.alicia)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    page = response.json()
    assert page["next_cursor"] is None
    items = page["items"]
    assert [i["action"] for i in items] == [  # más reciente primero
        "gestor_access.revoked",
        "gestor.note_added",
        "gestor.read",
        "gestor.read",
        "gestor_access.accepted",
        "gestor_access.invited",
    ]
    assert all(set(i) == KEYS for i in items)
    revoked, noted, clients, modelo, accepted, invited = items
    assert (revoked["actor_role"], revoked["actor_email"]) == ("usuario", None)
    assert (invited["actor_role"], invited["actor_email"]) == ("usuario", None)
    assert (accepted["actor_role"], accepted["actor_email"]) == ("gestor", cast.gina.email)
    assert (noted["entity_type"], noted["entity_id"], noted["actor_email"]) == (
        "gestor_note",
        note["id"],
        cast.gina.email,
    )
    assert (clients["entity_type"], clients["year"], clients["quarter"]) == ("clients", None, None)
    assert (modelo["entity_type"], modelo["year"], modelo["quarter"], modelo["actor_email"]) == (
        "modelo_130",
        2025,
        2,
        cast.gina.email,
    )
    assert "reservado" not in json.dumps(page)  # ni el texto de la anotación ni nada financiero
    assert [i["id"] for i in items] == sorted((i["id"] for i in items), reverse=True)


def test_the_pages_add_up_and_the_cursor_is_followed(api: Api, admin: Connection[DictRow]) -> None:
    owner = api.cast.alicia
    admin.execute(
        "insert into public.activity_log (category, actor_id, actor_role, owner_id, action, entity_type) "
        "select 'access', %s, 'gestor', %s, 'gestor.read', 'clients' from generate_series(1, 120)",
        (api.cast.gina.id, owner.id),
    )
    first = activity(api, owner).json()
    assert len(first["items"]) == 50 and first["next_cursor"] is not None
    second = activity(api, owner, cursor=first["next_cursor"]).json()
    third = activity(api, owner, cursor=second["next_cursor"]).json()
    ids = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert len(ids) == 120 and len(set(ids)) == 120 and ids == sorted(ids, reverse=True)
    assert len(third["items"]) == 20 and third["next_cursor"] is None


def test_a_bad_cursor_is_refused(api: Api) -> None:
    for cursor in ("abc", "-1", "1.5", "", "9" * 30, "1; drop table x"):
        response = activity(api, api.cast.alicia, cursor=cursor)
        assert (response.status_code, response.json()["code"]) == (422, "invalid_cursor"), cursor


def test_only_the_owner_reads_their_trail_and_only_the_access_category(
    api: Api, admin: Connection[DictRow], app_pool: Pool
) -> None:
    cast = api.cast
    access = api.invited(cast.alicia, cast.gina.email)
    api.accept(cast.gina, access)
    api.request("GET", f"/api/gestor/autonomos/{cast.alicia.id}/perfil", cast.gina)
    assert activity(api, cast.beto).json() == {"items": [], "next_cursor": None}
    for who in ("gina", "gus", "adan"):
        response = activity(api, cast[who])
        assert (response.status_code, response.json()["code"]) == (403, "forbidden"), who
    assert activity(api, None).status_code == 401
    admin.execute(
        "insert into public.activity_log (category, owner_id, action) values ('data', %s, 'invoice.issued')",
        (cast.alicia.id,),
    )
    assert {i["action"] for i in activity(api, cast.alicia).json()["items"]} <= {
        "gestor_access.invited",
        "gestor_access.accepted",
        "gestor.read",
    }  # las entradas de datos (facturas) no salen aquí


def test_an_empty_account_has_an_empty_trail(api: Api) -> None:
    assert activity(api, api.cast.alicia).json() == {"items": [], "next_cursor": None}
    assert uuid.UUID(str(api.cast.alicia.id))
