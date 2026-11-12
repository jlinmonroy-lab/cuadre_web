"""SPEC-W-010 hito 2 · Lo que las mutaciones pidieron cubrir: el dueño de la lectura no sobrevive a la transacción, el borde exacto de la paginación y que ninguna lectura se cachea."""

from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.gestor.support import documents, link
from tests.rls.expenses_support import insert, manual
from tests.support import Pool, call


def test_the_owner_chosen_for_a_read_does_not_stay_on_the_pooled_connection(api: Api, app_pool: Pool) -> None:
    """`cuadre.read_owner` es local a la transacción: si no lo fuera, la siguiente petición que reutilice la conexión miraría al autónomo del gestor."""
    cast = api.cast
    link(app_pool, cast.alicia, cast.gina)
    assert (
        api.request(
            "POST",
            "/api/clients",
            cast.beto,
            json=dict(name="Clientes de Beto S.L.", kind="business", country="ES", tax_id="B00000018", address=None),
        ).status_code
        == 201
    )
    for _ in range(8):  # el pool reutiliza conexiones: se alterna el gestor y el otro autónomo muchas veces
        assert api.request("GET", f"/api/gestor/autonomos/{cast.alicia.id}/clientes", cast.gina).status_code == 200
        mine = api.request("GET", "/api/clients", cast.beto).json()
        assert [c["name"] for c in mine] == ["Clientes de Beto S.L."]
        assert (
            api.request("GET", "/api/clients", cast.alicia).json() == []
        )  # y Alicia sigue viendo lo suyo, que es nada


def test_the_next_cursor_is_null_when_the_page_holds_exactly_what_is_left(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    cast = api.cast
    link(app_pool, cast.alicia, cast.gina)
    from datetime import date

    for n in range(4):
        insert(
            admin, manual(cast.alicia, date=date(2026, 3, 1 + n), name=f"Gasto {n}", base=1_000 + n, total=1_000 + n)
        )
    url = f"/api/gestor/autonomos/{cast.alicia.id}/gastos"
    exact = api.request("GET", url, cast.gina, params={"limit": 4}).json()
    assert len(exact["items"]) == 4 and exact["next_cursor"] is None
    short = api.request("GET", url, cast.gina, params={"limit": 3}).json()
    assert len(short["items"]) == 3 and short["next_cursor"] is not None
    assert (
        len(api.request("GET", url, cast.gina, params={"limit": 3, "page": short["next_cursor"]}).json()["items"]) == 1
    )


def test_no_gestor_read_can_be_cached(api: Api, app_pool: Pool) -> None:
    cast = api.cast
    link(app_pool, cast.alicia, cast.gina)
    documents(app_pool, cast.alicia, "review", 1)
    base = f"/api/gestor/autonomos/{cast.alicia.id}"
    urls: list[tuple[str, dict[str, Any] | None]] = [
        ("/api/gestor/cartera", None),
        (base, None),
        (f"{base}/facturas", None),
        (f"{base}/gastos", None),
        (f"{base}/documentos", None),
        (f"{base}/perfil", None),
        (f"{base}/clientes", None),
        (f"{base}/trimestres/303", {"year": 2025, "quarter": 1}),
        (f"{base}/trimestres/130", {"year": 2025, "quarter": 1}),
        (f"{base}/anotaciones", None),
    ]
    for url, params in urls:
        response = api.request("GET", url, cast.gina, params=params)
        assert response.status_code == 200, url
        assert response.headers["cache-control"] == "private, no-store", url
    for url in ("/api/gestor/anotaciones", "/api/gestor/actividad"):
        response = api.request("GET", url, cast.alicia)
        assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store", url
    created = api.request("POST", f"{base}/anotaciones", cast.gina, json={"body": "Hola"})
    assert created.headers["cache-control"] == "private, no-store"


def test_the_gestor_also_sees_the_archived_clients(api: Api, app_pool: Pool) -> None:
    """Salió de una mutación: ninguna prueba tenía un cliente archivado, y el gestor podía dejar de verlos sin que nada fallara."""
    cast = api.cast
    link(app_pool, cast.alicia, cast.gina)
    ids = []
    for name, tax_id in (("Cliente activo S.L.", "B00000018"), ("Cliente archivado S.L.", "B00000026")):
        created = api.request(
            "POST",
            "/api/clients",
            cast.alicia,
            json={"name": name, "kind": "business", "country": "ES", "tax_id": tax_id, "address": None},
        )
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    out = call(app_pool, cast.alicia, "set_client_archived", ids[1], True)
    assert not out.error, out.message
    theirs = api.request("GET", f"/api/gestor/autonomos/{cast.alicia.id}/clientes", cast.gina).json()
    assert {c["id"] for c in theirs} == set(ids)  # el archivado también
    assert [c["id"] for c in theirs if c["archived"]] == [ids[1]]
