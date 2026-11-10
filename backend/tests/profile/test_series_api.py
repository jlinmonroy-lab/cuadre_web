"""AC-09 a AC-13 · Las series por la API: la del año, crear, predeterminar, editar, archivar y los errores por código."""

import threading
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from cuadre.profile import repository
from tests.profile.conftest import VALID, Api
from tests.support import Cast, Pool


def codes(rows: list[dict[str, Any]]) -> list[str]:
    return [r["code"] for r in rows]


def test_ac09_reads_never_create_the_year_series(api: Api) -> None:
    api.profile(api.cast.alicia)
    assert api.series(api.cast.alicia) == []
    api.profile(api.cast.alicia)
    assert api.series(api.cast.alicia) == []


def test_ac09_the_first_save_creates_the_year_series_once(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    api.save(api.cast.alicia, **VALID)
    (year,) = api.series(api.cast.alicia)
    assert (year["code"], year["description"], year["first_number"], year["next_number"]) == (
        "2026",
        "Serie del año",
        1,
        1,
    )
    assert (year["is_default"], year["archived"], year["in_use"]) == (True, False, False)


def test_ac09_two_saves_at_once_leave_one_series(api: Api) -> None:
    results: list[int] = []

    def save() -> None:
        results.append(api.save(api.cast.alicia, **VALID).status_code)

    threads = [threading.Thread(target=save) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [200, 200]
    assert codes(api.series(api.cast.alicia)) == ["2026"]


def test_ac10_create_uppercases_and_is_not_default(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    response = api.request(
        "POST",
        "/api/invoice-series",
        api.cast.alicia,
        json={"code": "fac", "description": "Facturas", "first_number": 100},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["code"], body["first_number"], body["next_number"], body["is_default"]) == ("FAC", 100, 100, False)
    assert codes(api.series(api.cast.alicia)) == ["2026", "FAC"]  # la predeterminada primero


def test_ac10_a_repeated_or_archived_code_is_a_409(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    created = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "FAC"}).json()
    assert api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "FAC"}).json()["code"] == (
        "series_code_taken"
    )
    api.request("PATCH", f"/api/invoice-series/{created['id']}", api.cast.alicia, json={"archived": True})
    again = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "fac"})
    assert (again.status_code, again.json()["code"]) == (409, "series_code_taken")


@pytest.mark.parametrize("code", ["AB CD", "-A", "A-", "ABCDEFGHI", "", "ß"])
def test_ac10_a_bad_code_is_a_422(api: Api, code: str) -> None:
    response = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": code})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_series"
    assert response.json()["field"] == "code"


@pytest.mark.parametrize("number", [0, 1_000_000, -5])
def test_ac10_a_bad_first_number_is_a_422(api: Api, number: int) -> None:
    response = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "X", "first_number": number})
    assert (response.status_code, response.json()["field"]) == (422, "first_number")


def test_the_first_number_is_not_coerced_from_text_or_booleans(api: Api) -> None:
    for value in ("5", True, 5.5):
        response = api.request(
            "POST", "/api/invoice-series", api.cast.alicia, json={"code": "X", "first_number": value}
        )
        assert response.status_code == 422, value


def test_ac11_one_default_at_a_time(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    fac = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "FAC"}).json()
    done = api.request("PUT", f"/api/invoice-series/{fac['id']}/default", api.cast.alicia)
    assert done.status_code == 200
    assert [r["is_default"] for r in api.series(api.cast.alicia)] == [True, False]
    assert codes(api.series(api.cast.alicia)) == ["FAC", "2026"]
    api.request(
        "PATCH", f"/api/invoice-series/{fac['id']}", api.cast.alicia, json={"archived": True}
    )  # 409: es la predeterminada
    year = next(r for r in api.series(api.cast.alicia) if r["code"] == "2026")
    api.request("PUT", f"/api/invoice-series/{year['id']}/default", api.cast.alicia)
    assert (
        api.request("PATCH", f"/api/invoice-series/{fac['id']}", api.cast.alicia, json={"archived": True}).status_code
        == 200
    )
    archived = api.request("PUT", f"/api/invoice-series/{fac['id']}/default", api.cast.alicia)
    assert (archived.status_code, archived.json()["code"]) == (409, "series_archived")


def test_ac11_create_as_default_moves_the_mark(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "NEW", "make_default": True})
    assert codes(api.series(api.cast.alicia)) == ["NEW", "2026"]


def test_ac12_code_and_first_number_change_only_while_unused(api: Api, admin: Any) -> None:
    api.save(api.cast.alicia, **VALID)
    fac = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "FAC"}).json()
    path = f"/api/invoice-series/{fac['id']}"
    changed = api.request(
        "PATCH", path, api.cast.alicia, json={"code": "fa2", "first_number": 50, "description": "Nueva"}
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["code"], body["first_number"], body["next_number"], body["description"]) == ("FA2", 50, 50, "Nueva")
    admin.execute(
        "update public.invoice_series set next_number = 53 where id = %s", (fac["id"],)
    )  # una emisión simulada
    blocked = api.request("PATCH", path, api.cast.alicia, json={"first_number": 1})
    assert (blocked.status_code, blocked.json()["code"]) == (409, "series_in_use")
    assert api.request("PATCH", path, api.cast.alicia, json={"code": "OTRA"}).json()["code"] == "series_in_use"
    kept = api.request("PATCH", path, api.cast.alicia, json={"description": "Sigue editable"})
    assert (kept.status_code, kept.json()["in_use"]) == (200, True)
    same = api.request("PATCH", path, api.cast.alicia, json={"code": "FA2", "first_number": 50})
    assert same.status_code == 200  # el mismo valor no es un cambio
    assert same.json()["next_number"] == 53


def test_ac12_description_can_be_cleared_with_null(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    (year,) = api.series(api.cast.alicia)
    response = api.request("PATCH", f"/api/invoice-series/{year['id']}", api.cast.alicia, json={"description": None})
    assert response.json()["description"] is None


def test_ac13_archive_and_reactivate_but_never_the_default(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    (year,) = api.series(api.cast.alicia)
    default = api.request("PATCH", f"/api/invoice-series/{year['id']}", api.cast.alicia, json={"archived": True})
    assert (default.status_code, default.json()["code"]) == (409, "series_is_default")
    fac = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "FAC"}).json()
    path = f"/api/invoice-series/{fac['id']}"
    assert api.request("PATCH", path, api.cast.alicia, json={"archived": True}).json()["archived"] is True
    assert api.request("PATCH", path, api.cast.alicia, json={"archived": False}).json()["archived"] is False
    assert api.request("DELETE", path, api.cast.alicia).status_code == 405  # no hay forma de borrarlas


def test_a_foreign_or_unknown_series_is_a_404(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    (year,) = api.series(api.cast.alicia)
    foreign = api.request("PATCH", f"/api/invoice-series/{year['id']}", api.cast.beto, json={"description": "x"})
    assert (foreign.status_code, foreign.json()["code"]) == (404, "series_not_found")
    missing = api.request("PUT", "/api/invoice-series/00000000-0000-4000-8000-000000000000/default", api.cast.alicia)
    assert (missing.status_code, missing.json()["code"]) == (404, "series_not_found")
    assert api.series(api.cast.beto) == []


def test_a_rectifying_code_is_refused_to_create_and_to_rename(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    created = api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "FAC"}).json()
    for response in (
        api.request("POST", "/api/invoice-series", api.cast.alicia, json={"code": "R-2027"}),
        api.request("PATCH", f"/api/invoice-series/{created['id']}", api.cast.alicia, json={"code": "R-2027"}),
    ):
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "invalid_series" and body["field"] == "code"
        assert "rectificativas" in body["detail"]
    assert codes(api.series(api.cast.alicia)) == ["2026", "FAC"]


def test_the_rectifying_series_is_not_listed_nor_reachable(api: Api, admin: Connection[DictRow]) -> None:
    """La serie `R-AAAA` la crea la emisión (SPEC-W-007): Perfil no la enseña, y las rutas de series la tratan como inexistente."""
    api.save(api.cast.alicia, **VALID)
    admin.execute(
        "insert into public.invoice_series (owner_id, code, kind) values (%s, 'R-2026', 'rectifying') returning id",
        (api.cast.alicia.id,),
    )
    rectifying = admin.execute(
        "select id from public.invoice_series where owner_id = %s and code = 'R-2026'", (api.cast.alicia.id,)
    ).fetchone()
    assert rectifying is not None
    assert codes(api.series(api.cast.alicia)) == ["2026"]
    response = api.request(
        "PATCH", f"/api/invoice-series/{rectifying['id']}", api.cast.alicia, json={"description": "x"}
    )
    assert response.status_code == 404


def test_the_database_refusal_of_a_reserved_code_is_a_field_error(app_pool: Pool, cast: Cast) -> None:
    """Si alguien llega a la base sin pasar por el dominio, la base responde `series_code_reserved` y la API lo traduce igual."""
    with pytest.raises(psycopg.Error) as info, user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select app.create_invoice_series('R-2027', null, 1, false)")
    problem = repository.translate_db_error(info.value)
    assert problem is not None
    assert (problem.status, problem.code, problem.extra["field"]) == (422, "invalid_series", "code")
    assert "rectificativas" in problem.detail
