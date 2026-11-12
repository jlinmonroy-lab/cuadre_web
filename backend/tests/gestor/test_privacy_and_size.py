"""AC-18, AC-23 · Sin datos en los registros de las lecturas del gestor y cada respuesta cabe en una Vercel Function (SPEC-W-010 hito 2)."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.agents.support import captured_logs, rendered
from tests.gestor.conftest import Api
from tests.gestor.support import link
from tests.quarters.conftest import Seeded, seed
from tests.support import Pool

LIMIT_BYTES = 4_500_000


@pytest.fixture(scope="module")
def seeded(admin: Connection[DictRow], app_pool: Pool) -> Iterator[Seeded]:
    data = seed(admin, app_pool)
    link(app_pool, data.cast.alicia, data.cast.gina)
    yield data


def test_no_log_line_of_the_requests_carries_names_amounts_or_numbers(api: Api, seeded: Seeded) -> None:
    base = f"/api/gestor/autonomos/{seeded.cast.alicia.id}"
    with captured_logs("cuadre") as records:
        listing = api.request("GET", f"{base}/facturas", seeded.cast.gina, params={"year": 2025, "limit": 200}).json()
        for suffix in (
            "/perfil",
            "/clientes",
            "/gastos",
            "/documentos",
            "/trimestres/303?year=2025&quarter=2",
            "/trimestres/130?year=2025&quarter=2",
        ):
            assert api.request("GET", f"{base}{suffix}", seeded.cast.gina).status_code == 200
        api.request("GET", f"{base}/facturas/{listing[0]['id']}", seeded.cast.gina)
        api.request("POST", f"{base}/anotaciones", seeded.cast.gina, json={"body": "Texto reservado de la anotación"})
    seen = rendered(records)
    for secret in (
        "2025-001",
        "R-2025-001",
        "Emisor Sintético",
        "12345678Z",
        "ES3600000000050000000001",
        "Cliente",
        "reservado",
        seeded.cast.alicia.email,
    ):
        assert secret not in seen, secret


def test_the_worst_admissible_page_of_each_list_fits_in_a_function_response(api: Api, seeded: Seeded) -> None:  # AC-23
    base = f"/api/gestor/autonomos/{seeded.cast.alicia.id}"
    invoices = api.request("GET", f"{base}/facturas", seeded.cast.gina, params={"year": 2025, "limit": 200}).json()
    expenses = api.request("GET", f"{base}/gastos", seeded.cast.gina, params={"limit": 100}).json()["items"]
    assert invoices and expenses
    worst_invoice = max(len(json.dumps(i)) for i in invoices)
    worst_expense = max(len(json.dumps(e)) for e in expenses)
    assert worst_invoice * 200 < LIMIT_BYTES, worst_invoice  # 200 facturas por página
    assert worst_expense * 100 < LIMIT_BYTES, worst_expense  # 100 gastos por página


def test_the_portfolio_and_the_activity_are_bounded_by_construction(api: Api, seeded: Seeded) -> None:
    from cuadre.gestor.reads import ACTIVITY_PAGE, NOTES_LIMIT

    assert ACTIVITY_PAGE <= 50 and NOTES_LIMIT <= 200
    row: dict[str, Any] = {"id": "x" * 36, "name": "N" * 200, "email": "e" * 254, "pending_count": 99_999}
    assert len(json.dumps(row)) * 5_000 < LIMIT_BYTES  # 5.000 autónomos con los datos más largos caben
