"""AC-14 · El gestor solo lee (CONF-001 a): no hay rutas que escriban la contabilidad del autónomo y la base rechaza cualquier escritura suya (SPEC-W-010 hito 2)."""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.gestor.support import link
from tests.support import Pool, attempt, call, load_matrix

SRC = Path(__file__).resolve().parents[2] / "src" / "cuadre"
MATRIX = load_matrix()
FINANCIAL = [name for name, spec in MATRIX["tables"].items() if spec["kind"] == "financial"]


def test_under_autonomos_the_only_route_that_writes_is_the_note(app: FastAPI) -> None:
    paths = app.openapi()["paths"]
    written = sorted(
        (method.upper(), path)
        for path, item in paths.items()
        if path.startswith("/api/gestor/autonomos/")
        for method in item
        if method != "get"
    )
    assert written == [("POST", "/api/gestor/autonomos/{owner_id}/anotaciones")]


def test_the_gestor_routes_are_a_closed_list(app: FastAPI) -> None:
    gestor = sorted(
        f"{method.upper()} {path}"
        for path, item in app.openapi()["paths"].items()
        if path.startswith("/api/gestor")
        for method in item
    )
    assert len(gestor) == 22, gestor  # 6 de acceso del hito 1 + 16 de lectura, anotaciones y actividad del hito 2


@pytest.mark.parametrize("table", FINANCIAL)
def test_a_gestor_with_an_active_link_changes_nothing_in_any_financial_table(
    api: Api, app_pool: Pool, admin: Connection[DictRow], table: str
) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    spec = MATRIX["tables"][table]
    if seed := spec.get("seed"):
        admin.execute(seed, {"owner": api.cast.alicia.id})
    owner_column, probe = spec["owner_column"], spec["probe_update"]
    params = {"owner": api.cast.alicia.id, "email": f"x.{api.cast.alicia.email}", "value": probe["value"]}
    update = attempt(
        app_pool,
        api.cast.gina,
        f'update public."{table}" set "{probe["column"]}" = %(value)s where "{owner_column}" = %(owner)s',
        params,
    )
    delete = attempt(
        app_pool, api.cast.gina, f'delete from public."{table}" where "{owner_column}" = %(owner)s', params
    )
    insert = attempt(app_pool, api.cast.gina, spec["probe_insert"], params)
    assert update.blocked and delete.blocked and insert.error, table
    changed = admin.execute(
        f'select count(*) as n from public."{table}" where "{owner_column}" = %s and "{probe["column"]}"::text = %s',
        (api.cast.alicia.id, probe["value"]),
    ).fetchone()
    assert changed is not None and changed["n"] == 0, table


@pytest.mark.parametrize(
    ("function", "args"),
    [
        ("create_client", ("Cliente", "business", "ES", None, None, None, None)),
        ("set_client_archived", ("00000000-0000-4000-8000-000000000001", True)),
        ("void_expense", ("00000000-0000-4000-8000-000000000001",)),
    ],
)
def test_the_functions_that_write_for_the_owner_refuse_a_gestor(
    api: Api, app_pool: Pool, function: str, args: tuple[object, ...]
) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    assert call(app_pool, api.cast.gina, function, *args).sqlstate == "42501"


def test_no_gestor_code_uses_the_service_key_or_the_service_database() -> None:
    forbidden = (
        "database_service_url",
        "service_role",
        "SERVICE_ROLE",
        "supabase_service_role_key",
        "cuadre.jobs",
    )
    for path in [
        *(SRC / "gestor").glob("*.py"),
        SRC / "api" / "routes_gestor.py",
        SRC / "api" / "routes_gestor_reads.py",
    ]:
        text = path.read_text(encoding="utf-8")
        for word in forbidden:
            assert word not in text, (path.name, word)
        assert re.search(r"cuadre\.cli" + r"\b", text) is None, (
            path.name
        )  # `cuadre.cli` (no `cuadre.clients`) es solo de la línea de órdenes
