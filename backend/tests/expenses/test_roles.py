"""AC-15 (lado API), T3-07 · Solo `usuario` usa las rutas de gastos; un gasto ajeno responde igual que uno inexistente.

El aislamiento por RLS lo prueba `tests/rls/`. Aquí se comprueba que la API no abre ningún hueco por encima: el rol sale de la base de datos y
no del token, y los gestores (aunque tengan vínculo activo) y los administradores no entran (D3, CONF-001).
"""

from typing import Any
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.documents.conftest import Api
from tests.expenses.support import all_expenses, manual, read, registered
from tests.support import Pool, apply_scenario

GHOST = uuid4()
MANUAL_BODY = {"expense_date": "2026-10-01", "concept": "Cuota", "category": "other", "amount_cents": 100}

# (método, plantilla de ruta, cuerpo)
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", "/api/expenses", MANUAL_BODY),
    ("GET", "/api/expenses", None),
    ("GET", "/api/expenses/{id}", None),
    ("PUT", "/api/expenses/{id}/category", {"category": "other"}),
    ("POST", "/api/expenses/{id}/void", None),
    ("POST", "/api/documents/{id}/confirm", {"category": "software"}),
]
ROUTE_IDS = [f"{m} {u}" for m, u, _ in ROUTES]


def call(api: Api, person: Any, route: tuple[str, str, dict[str, Any] | None], target: object = GHOST) -> Any:
    method, url, body = route
    return api.request(method, url.replace("{id}", str(target)), person, **({"json": body} if body is not None else {}))


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize("who", ["gina", "adan"])
def test_gestores_and_admins_get_403_on_every_route(api: Api, admin: Connection[DictRow], who: str, route: Any) -> None:
    response = call(api, api.cast[who], route)
    assert response.status_code == 403 and response.json()["code"] == "forbidden"
    assert all_expenses(admin, api.cast[who]) == []


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_a_gestor_with_an_active_link_still_cannot_use_these_routes(api: Api, app_pool: Pool, route: Any) -> None:
    """Ver los gastos de sus usuarios es de SPEC-W-010; aquí el gestor no entra ni leyendo."""
    alicia, gina = api.cast.alicia, api.cast.gina
    document_id, expense = registered(api, alicia)
    apply_scenario(app_pool, api.cast, "active")
    target = document_id if "/documents/" in route[1] else expense["id"]

    response = call(api, gina, route, target)

    assert response.status_code == 403 and response.json()["code"] == "forbidden", response.text
    assert "Nubesoft" not in response.text and expense["id"] not in response.text


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_without_a_session_it_is_a_401(api: Api, route: Any) -> None:
    method, url, body = route
    response = api.client.request(
        method, url.replace("{id}", str(GHOST)), **({"json": body} if body is not None else {})
    )
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_the_role_comes_from_the_database_not_from_the_token(api: Api, admin: Connection[DictRow], route: Any) -> None:
    """Una degradación surte efecto en la petición siguiente, con el mismo token."""
    alicia = api.cast.alicia
    assert call(api, alicia, ROUTES[1]).status_code == 200
    admin.execute("update public.profiles set role = 'gestor' where id = %s", (alicia.id,))
    response = call(api, alicia, route)
    assert response.status_code == 403 and response.json()["code"] == "forbidden"


def test_a_suspended_account_gets_403_account_suspended(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (alicia.id,))
    response = call(api, alicia, ROUTES[1])
    assert response.status_code == 403 and response.json()["code"] == "account_suspended"


def test_a_foreign_expense_answers_exactly_like_one_that_does_not_exist(api: Api) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    mine = manual(api, alicia)
    for route in ROUTES[2:5]:
        foreign = call(api, beto, route, mine["id"])
        ghost = call(api, beto, route, GHOST)
        assert foreign.status_code == ghost.status_code == 404, route
        strip = {"request_id"}
        assert {k: v for k, v in foreign.json().items() if k not in strip} == {
            k: v for k, v in ghost.json().items() if k not in strip
        }, route
    assert api.request("GET", f"/api/expenses/{mine['id']}", alicia).status_code == 200


def test_a_foreign_document_cannot_be_confirmed_and_a_foreign_list_is_empty(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    document_id = read(api, alicia)
    manual(api, alicia)
    response = call(api, beto, ROUTES[5], document_id)
    assert response.status_code == 404 and response.json()["code"] == "document_not_found"
    assert api.request("GET", "/api/expenses", beto).json() == {"items": [], "next_cursor": None}
    assert all_expenses(admin, beto) == []
