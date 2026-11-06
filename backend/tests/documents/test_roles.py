"""AC-07, T2-06 (lado API) · Solo `usuario` usa las rutas de documentos; un documento ajeno responde igual que uno inexistente.

El aislamiento por RLS y por Storage lo prueban `tests/rls/`. Aquí se comprueba que la API no abre ningún hueco por encima: el rol sale
de la base de datos, no del token, y los gestores (aunque tengan vínculo activo) y los administradores no entran (D3, CONF-001).
"""

from typing import Any
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from cuadre.documents import repository
from tests.documents.conftest import Api, db_row
from tests.support import Pool, apply_scenario

GHOST = uuid4()

# (método, plantilla de ruta, cuerpo)
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    (
        "POST",
        "/api/documents",
        {"filename": "a.pdf", "mime_type": "application/pdf", "size_bytes": 10, "source": "file"},
    ),
    ("GET", "/api/documents", None),
    ("GET", "/api/documents/{id}", None),
    ("GET", "/api/documents/{id}/preview", None),
    ("POST", "/api/documents/{id}/complete", None),
    ("POST", "/api/documents/{id}/retry", None),
    ("PUT", "/api/documents/{id}/review", {"supplier_name": "x"}),
    ("DELETE", "/api/documents/{id}", None),
]
ROUTE_IDS = [f"{m} {u}" for m, u, _ in ROUTES]
ROUTES_WITH_ID = [r for r in ROUTES if "{id}" in r[1]]


def call(api: Api, person: Any, route: tuple[str, str, dict[str, Any] | None], document_id: object = GHOST) -> Any:
    method, url, body = route
    return api.request(
        method, url.replace("{id}", str(document_id)), person, **({"json": body} if body is not None else {})
    )


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize("who", ["gina", "adan"])
def test_gestores_and_admins_get_403_on_every_route(api: Api, who: str, route: Any) -> None:
    response = call(api, api.cast[who], route)
    assert response.status_code == 403 and response.json()["code"] == "forbidden"
    assert api.storage.calls == []


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_a_gestor_with_an_active_link_still_cannot_use_these_routes(api: Api, app_pool: Pool, route: Any) -> None:
    """Ver los documentos de sus usuarios es de SPEC-W-010; aquí el gestor no entra ni leyendo."""
    alicia, gina = api.cast.alicia, api.cast.gina
    document_id = api.read(alicia)
    apply_scenario(app_pool, api.cast, "active")
    response = call(api, gina, route, document_id)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_without_a_session_every_route_is_401(api: Api, route: Any) -> None:
    method, url, body = route
    response = api.client.request(
        method, url.replace("{id}", str(GHOST)), **({"json": body} if body is not None else {})
    )
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"


def test_a_tampered_token_is_401(api: Api) -> None:
    token = api.token(api.cast.alicia)
    header, payload, signature = token.split(".")
    bad = f"{header}.{payload}.{signature[:-3]}AAA"
    response = api.client.get("/api/documents", headers={"Authorization": f"Bearer {bad}"})
    assert response.status_code == 401


def test_the_role_comes_from_the_database_not_from_the_token(api: Api, admin: Connection[DictRow]) -> None:
    gina = api.cast.gina
    token = api.signer.token(gina, app_metadata={"role": "usuario"}, user_metadata={"role": "usuario"})
    headers = {"Authorization": f"Bearer {token}"}
    assert api.client.get("/api/documents", headers=headers).status_code == 403, "el token pide ser usuario y se ignora"
    admin.execute("update public.profiles set role = 'usuario' where id = %s", (gina.id,))
    assert api.client.get("/api/documents", headers=headers).status_code == 200, "rige el cambio en la base de datos"


def test_a_suspended_account_cannot_use_the_routes(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (alicia.id,))
    response = api.request("GET", "/api/documents", alicia)
    assert response.status_code == 403 and response.json()["code"] == "account_suspended"


# --- Documentos ajenos ----------------------------------------------------------------------------------------------------------


def problem_without_request_id(response: Any) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    body.pop("request_id", None)
    return body


@pytest.mark.parametrize("route", ROUTES_WITH_ID, ids=lambda r: f"{r[0]} {r[1]}")
def test_ac07_someone_elses_document_answers_exactly_like_one_that_does_not_exist(
    api: Api, admin: Connection[DictRow], route: Any
) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    document_id = api.read(alicia)
    before = db_row(admin, document_id)

    foreign = call(api, beto, route, document_id)
    missing = call(api, beto, route, GHOST)
    assert foreign.status_code == 404 and missing.status_code == 404
    assert problem_without_request_id(foreign) == problem_without_request_id(missing)
    assert problem_without_request_id(foreign)["code"] == "document_not_found"

    assert db_row(admin, document_id) == before, "nada cambió"
    assert api.storage.operations("delete") == []


def test_each_person_only_lists_their_own_documents(api: Api) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    mine = api.read(alicia)
    theirs = api.read(beto)
    assert [r["id"] for r in api.request("GET", "/api/documents", alicia).json()] == [str(mine)]
    assert [r["id"] for r in api.request("GET", "/api/documents", beto).json()] == [str(theirs)]


def test_a_malformed_document_id_is_422_not_a_server_error(api: Api) -> None:
    response = api.request("GET", "/api/documents/no-es-un-uuid", api.cast.alicia)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_the_owner_filter_in_the_queries_holds_even_where_rls_would_let_a_gestor_read(api: Api, app_pool: Pool) -> None:
    """Defensa en profundidad: aunque una ruta futura dejase pasar a un gestor, las consultas de documentos filtran por propietario."""
    alicia, gina = api.cast.alicia, api.cast.gina
    document_id = api.read(alicia)
    apply_scenario(app_pool, api.cast, "active")
    with user_transaction(app_pool, gina.id) as conn:
        row = conn.execute("select count(*) as n from public.documents where id = %s", (document_id,)).fetchone()
        assert row is not None and row["n"] == 1, "precondición: la RLS sí deja leer al gestor con vínculo activo"
        assert repository.get(conn, document_id) is None
        assert repository.list_visible(conn) == []
