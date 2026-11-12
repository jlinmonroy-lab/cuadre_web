"""AC-15 · Anotaciones por la API: el gestor las crea y las lee, el autónomo las ve, solo se añaden y se pierde el acceso al revocar (SPEC-W-010 hito 2)."""

import uuid
from datetime import date
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.gestor.support import access_log, link
from tests.rls.expenses_support import insert, manual
from tests.support import Pool, make_cast

KEYS = {"id", "body", "entity_type", "entity_id", "created_at", "gestor_email"}


def url(api: Api) -> str:
    return f"/api/gestor/autonomos/{api.cast.alicia.id}/anotaciones"


def post(api: Api, who: object, body: object = "Revisa el IVA de marzo", **fields: Any) -> Any:
    return api.request("POST", url(api), who, json={"body": body, **fields})  # type: ignore[arg-type]


def test_a_gestor_adds_a_note_and_reads_it_back_and_the_owner_sees_it_with_the_gestors_email(
    api: Api, app_pool: Pool
) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    response = post(api, api.cast.gina, "  Falta el justificante de marzo  ")
    assert response.status_code == 201, response.text
    created = response.json()
    assert set(created) == KEYS and created["body"] == "Falta el justificante de marzo"
    assert (created["entity_type"], created["entity_id"], created["gestor_email"]) == (None, None, None)
    assert response.headers["cache-control"] == "private, no-store"

    theirs = api.request("GET", url(api), api.cast.gina).json()
    assert [n["id"] for n in theirs] == [created["id"]]
    mine = api.request("GET", "/api/gestor/anotaciones", api.cast.alicia).json()
    assert [(n["id"], n["body"], n["gestor_email"]) for n in mine] == [
        (created["id"], created["body"], api.cast.gina.email)
    ]


def test_a_note_can_point_to_an_expense_and_keeps_the_link(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    expense = insert(
        admin, manual(api.cast.alicia, date=date(2026, 3, 3), name="Gasto anotado", base=1_000, total=1_000)
    )
    created = post(api, api.cast.gina, "Mira esto", entity_type="expense", entity_id=str(expense)).json()
    assert (created["entity_type"], created["entity_id"]) == ("expense", str(expense))


def test_the_length_is_one_to_two_thousand_characters_and_the_link_must_be_of_that_client(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    assert post(api, api.cast.gina, "x").status_code == 201
    assert post(api, api.cast.gina, "y" * 2000).status_code == 201
    for bad in ("", "   ", "z" * 2001):
        response = post(api, api.cast.gina, bad)
        assert (response.status_code, response.json()["code"]) == (422, "invalid_note"), bad[:5]
        assert response.json()["fields"][0]["field"] == "body"
    foreign = insert(
        admin, manual(make_cast(admin).alicia, date=date(2026, 3, 3), name="Ajeno", base=1_000, total=1_000)
    )
    for fields in (
        {"entity_type": "expense", "entity_id": str(foreign)},
        {"entity_type": "expense", "entity_id": str(uuid.uuid4())},
    ):
        response = post(api, api.cast.gina, "Hola", **fields)
        assert (response.status_code, response.json()["code"]) == (422, "invalid_note")
        assert response.json()["fields"][0]["field"] == "entity"
    for fields in ({"entity_type": "expense"}, {"entity_id": str(uuid.uuid4())}):
        assert post(api, api.cast.gina, "Hola", **fields).json()["fields"][0]["field"] == "entity"


def test_a_body_that_is_not_text_or_a_type_that_does_not_exist_is_a_validation_error(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    for payload in (
        {},
        {"body": 5},
        {"body": "x" * 4001},
        {"body": "Hola", "entity_type": "client", "entity_id": str(uuid.uuid4())},
    ):
        response = api.request("POST", url(api), api.cast.gina, json=payload)
        assert (response.status_code, response.json()["code"]) == (422, "validation_error"), payload


def test_nobody_else_creates_or_reads_them(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    note = post(api, api.cast.gina).json()
    for who in ("gus",):  # un gestor sin vínculo
        assert post(api, api.cast[who]).status_code == 404
        assert api.request("GET", url(api), api.cast[who]).status_code == 404
    for who in ("alicia", "beto", "adan"):  # el rol decide antes
        assert post(api, api.cast[who]).status_code == 403
        assert api.request("GET", url(api), api.cast[who]).status_code == 403
    # Otro autónomo no ve las anotaciones de Alicia; un gestor no usa la ruta del autónomo.
    assert api.request("GET", "/api/gestor/anotaciones", api.cast.beto).json() == []
    assert api.request("GET", "/api/gestor/anotaciones", api.cast.gina).status_code == 403
    assert [n["id"] for n in api.request("GET", "/api/gestor/anotaciones", api.cast.alicia).json()] == [note["id"]]


def test_each_gestor_reads_only_their_own_notes_even_with_the_same_client(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    link(app_pool, api.cast.alicia, api.cast.gus)
    mine = post(api, api.cast.gina, "De Gina").json()
    other = post(api, api.cast.gus, "De Gus").json()
    assert [n["id"] for n in api.request("GET", url(api), api.cast.gina).json()] == [mine["id"]]
    assert [n["id"] for n in api.request("GET", url(api), api.cast.gus).json()] == [other["id"]]
    assert {
        n["id"]: n["gestor_email"] for n in api.request("GET", "/api/gestor/anotaciones", api.cast.alicia).json()
    } == {
        mine["id"]: api.cast.gina.email,
        other["id"]: api.cast.gus.email,
    }


def test_after_revoking_the_gestor_neither_creates_nor_reads_but_the_owner_keeps_the_notes(
    api: Api, app_pool: Pool
) -> None:
    access = link(app_pool, api.cast.alicia, api.cast.gina)
    note = post(api, api.cast.gina).json()
    assert api.revoke(api.cast.alicia, access).status_code == 204
    assert post(api, api.cast.gina).status_code == 404
    assert api.request("GET", url(api), api.cast.gina).status_code == 404
    assert [n["id"] for n in api.request("GET", "/api/gestor/anotaciones", api.cast.alicia).json()] == [note["id"]]


def test_there_are_no_routes_to_edit_or_delete_a_note(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    note = post(api, api.cast.gina).json()
    for method in ("PUT", "PATCH", "DELETE"):
        response = api.request(method, f"{url(api)}/{note['id']}", api.cast.gina)
        assert response.status_code in (404, 405), method


def test_creating_a_note_is_logged_with_ids_only(api: Api, app_pool: Pool, admin: Connection[DictRow]) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    note = post(api, api.cast.gina, "Texto reservado de la anotación").json()
    entry = [r for r in access_log(admin, api.cast.alicia) if r["action"] == "gestor.note_added"]
    assert [(r["entity_type"], r["entity_id"], r["metadata"]) for r in entry] == [("gestor_note", note["id"], {})]
    assert "reservado" not in str(access_log(admin, api.cast.alicia))
