"""AC-13 a AC-18, AC-22 y AC-23 · `GET /api/tax/130`: el borrador del modelo 130 por HTTP, con la aplicación real y la base real (SPEC-W-009 §5.3, hito 3).

Los 23 documentos de B.1 están sembrados con las funciones de la base (ver `conftest.py`). Aquí se piden por la API y se comprueba que el JSON dice lo que
dijo la persona a mano: las siete casillas, el resultado, el porcentaje con retención, los documentos de cada casilla, el plazo, los errores y los avisos. Una
lectura no escribe y nada de lo que lee (proveedores, números de factura, importes) va a los registros.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.quarters.models import present_130
from cuadre.tax import IncomeRow, build_modelo_130
from cuadre.tax.limits import YEAR_MAX_DOCUMENTS
from tests.agents.support import captured_logs, rendered
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.clocks import FixedClock
from tests.invoicing.conftest import app  # noqa: F401 - fixture de otro conftest
from tests.quarters.conftest import Seeded
from tests.rls.expenses_support import insert, params
from tests.support import Person, Pool, apply_scenario, make_cast, new_document
from tests.tax.test_modelo_130_cases import EVERY_CASE

URL = "/api/tax/130"
CODES = ["01", "02", "03", "04", "05", "06", "07"]
CASE_IDS = [c["caso"] for c in EVERY_CASE]
ITEM_KEYS = {"kind", "id", "label", "date", "amount_cents"}


def at(day: str) -> FixedClock:
    return FixedClock(datetime.fromisoformat(day).replace(hour=12, tzinfo=UTC))


@dataclass
class Http:
    app: FastAPI
    client: TestClient
    signer: Signer

    def get(self, person: Person | None, *, url: str = URL, **query: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.signer.token(person)}"} if person is not None else {}
        return self.client.get(url, headers=headers, params=query or None)

    def now(self, day: str) -> None:
        self.app.state.clock = at(day)


@pytest.fixture
def http(app: FastAPI, signer: Signer) -> Any:  # noqa: F811
    with TestClient(app, raise_server_exceptions=False) as client:
        server = Http(app, client, signer)
        server.now("2026-06-01")
        yield server


def codes(body: dict[str, Any]) -> list[str]:
    return [b["code"] for b in body["boxes"]]


def box(body: dict[str, Any], code: str) -> dict[str, Any]:
    return next(b for b in body["boxes"] if b["code"] == code)


# --- AC-15, NFR-08 · los ejercicios por HTTP -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", EVERY_CASE, ids=CASE_IDS)
def test_the_api_returns_the_hand_calculated_boxes_with_their_documents(
    http: Http, seeded_130: Seeded, case: dict
) -> None:
    response = http.get(seeded_130.cast.alicia, year=case["anio"], quarter=case["trimestre"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert codes(body) == CODES
    assert {b["code"]: b["amount_cents"] for b in body["boxes"]} == case["casillas"]
    assert (body["result_kind"], body["result_cents"]) == (case["resultado"], case["casillas"]["07"])
    assert body["withheld_share_percent"] == case["porcentaje_retencion"]
    for b in body["boxes"]:
        got = [i["id"] if i["kind"] == "quarter" else seeded_130.from_db[i["id"]] for i in b["items"]]
        assert got == case["documentos"].get(b["code"], []), f"{case['caso']} casilla {b['code']}"
        if b["items"]:  # NFR-08: la suma de lo que aporta cada documento es la casilla
            assert sum(i["amount_cents"] for i in b["items"]) == b["amount_cents"]


def test_the_shape_of_the_response_and_its_headers(http: Http, seeded_130: Seeded) -> None:
    response = http.get(seeded_130.cast.alicia, year=2025, quarter=2)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {
        "year", "quarter", "period_start", "period_end", "deadline", "deadline_status", "boxes", "result_cents",
        "result_kind", "withheld_share_percent", "notes",
    }  # fmt: skip
    # Acumulado: empieza el 1 de enero aunque se pida el segundo trimestre.
    assert (body["period_start"], body["period_end"], body["deadline"]) == ("2025-01-01", "2025-07-01", "2025-07-20")
    assert {b["code"]: b["group"] for b in body["boxes"]} == {
        "01": "rendimiento", "02": "rendimiento", "03": "rendimiento", "04": "rendimiento", "05": "pagos",
        "06": "pagos", "07": "resultado",
    }  # fmt: skip
    assert {b["code"]: b["components"] for b in body["boxes"] if b["components"]} == {
        "03": ["01", "02"], "04": ["03"], "07": ["04", "05", "06"],
    }  # fmt: skip
    assert all(not b["items"] for b in body["boxes"] if b["components"])
    invoice = box(body, "01")["items"][0]
    assert set(invoice) == ITEM_KEYS and invoice["kind"] == "invoice"
    assert uuid.UUID(invoice["id"]) and invoice["label"] == "2025-001" and invoice["date"] == "2025-01-15"
    expense = box(body, "02")["items"][0]
    assert (expense["kind"], expense["label"], expense["amount_cents"]) == ("expense", "G1", 40_000)  # IVA deducible
    previous = box(body, "05")["items"][0]
    assert set(previous) == ITEM_KEYS
    assert (previous["kind"], previous["id"], previous["label"], previous["date"]) == (
        "quarter", "T1", "T1 de 2025", "2025-03-31",
    )  # fmt: skip


# --- AC-13 · el plazo y su estado --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "year", "quarter", "deadline", "status"),
    [
        ("2026-03-31", 2026, 1, "2026-04-20", "en_curso"),
        ("2026-04-01", 2026, 1, "2026-04-20", "plazo_abierto"),
        ("2026-04-20", 2026, 1, "2026-04-20", "plazo_abierto"),
        ("2026-04-21", 2026, 1, "2026-04-20", "plazo_cerrado"),
        ("2026-01-30", 2025, 4, "2026-01-30", "plazo_abierto"),
        ("2026-01-31", 2025, 4, "2026-01-30", "plazo_cerrado"),
        ("2025-12-31", 2025, 4, "2026-01-30", "en_curso"),
    ],
)
def test_the_deadline_and_its_status_follow_the_clock_and_are_the_ones_of_the_303(
    http: Http, seeded_130: Seeded, today: str, year: int, quarter: int, deadline: str, status: str
) -> None:  # AC-13
    http.now(today)
    body = http.get(seeded_130.cast.alicia, year=year, quarter=quarter).json()
    assert (body["deadline"], body["deadline_status"]) == (deadline, status)
    other = http.get(seeded_130.cast.alicia, url="/api/tax/303", year=year, quarter=quarter).json()
    assert (other["deadline"], other["deadline_status"]) == (deadline, status)


# --- Por defecto: el trimestre en curso (Madrid) ---------------------------------------------------------------------------------------


def test_without_parameters_it_is_the_current_quarter_in_madrid(http: Http, seeded_130: Seeded) -> None:
    http.now("2026-06-01")
    body = http.get(seeded_130.cast.alicia).json()
    assert (body["year"], body["quarter"]) == (2026, 2)
    assert [i["label"] for i in box(body, "01")["items"]] == ["2026-001"]  # X1, del 01/04/2026
    # A las 23:30 UTC del 31 de marzo ya es 1 de abril en Madrid.
    http.app.state.clock = FixedClock(datetime(2026, 3, 31, 23, 30, tzinfo=UTC))
    again = http.get(seeded_130.cast.alicia).json()
    assert (again["year"], again["quarter"]) == (2026, 2)


def test_each_missing_parameter_defaults_on_its_own(http: Http, seeded_130: Seeded) -> None:
    http.now("2026-06-01")
    only_year = http.get(seeded_130.cast.alicia, year=2025).json()
    assert (only_year["year"], only_year["quarter"]) == (2025, 2)  # el trimestre de hoy, en ese año
    only_quarter = http.get(seeded_130.cast.alicia, quarter=1).json()
    assert (only_quarter["year"], only_quarter["quarter"]) == (2026, 1)


# --- AC-14 · el periodo -------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "quarter"), [(2025, 5), (2025, 0), (2025, -1), (1999, 1), (9999, 1), (10**20, 1), (2025, 10**20)]
)
def test_a_period_that_does_not_exist_is_invalid_period(
    http: Http, seeded_130: Seeded, year: int, quarter: int
) -> None:
    response = http.get(seeded_130.cast.alicia, year=year, quarter=quarter)
    assert response.status_code == 422 and response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "invalid_period"
    assert str(year) not in response.json()["detail"]  # no repite lo que se envió


@pytest.mark.parametrize(
    "query", [{"year": "abc", "quarter": 1}, {"year": 2025, "quarter": "1.5"}, {"year": "", "quarter": 1}]
)
def test_a_value_that_is_not_an_integer_is_a_validation_error(
    http: Http, seeded_130: Seeded, query: dict[str, Any]
) -> None:
    response = http.get(seeded_130.cast.alicia, **query)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_a_quarter_that_has_not_started_is_in_the_future_and_the_current_one_is_fine(
    http: Http, seeded_130: Seeded
) -> None:
    http.now("2026-06-01")
    for year, quarter in ((2026, 3), (2026, 4), (2027, 1)):
        response = http.get(seeded_130.cast.alicia, year=year, quarter=quarter)
        assert (response.status_code, response.json()["code"]) == (422, "period_in_future")
    assert http.get(seeded_130.cast.alicia, year=2026, quarter=2).status_code == 200


def test_a_period_error_is_answered_before_anything_is_read(
    http: Http, seeded_130: Seeded, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise AssertionError("no se debía leer la base de datos")

    monkeypatch.setattr("cuadre.quarters.service.user_transaction", boom)
    assert http.get(seeded_130.cast.alicia, year=2025, quarter=7).json()["code"] == "invalid_period"
    assert http.get(seeded_130.cast.alicia, year=2027, quarter=1).json()["code"] == "period_in_future"


# --- AC-18 · demasiados documentos --------------------------------------------------------------------------------------------------


def test_a_period_with_too_many_documents_is_refused_with_its_own_text(
    http: Http, seeded_130: Seeded, monkeypatch: pytest.MonkeyPatch
) -> None:
    # El T1 de 2025 acumula 4 facturas y 3 gastos vivos (G4 está anulado): 7 documentos. El T2 acumula más.
    monkeypatch.setattr("cuadre.tax.modelo_130.YEAR_MAX_DOCUMENTS", 7)
    assert http.get(seeded_130.cast.alicia, year=2025, quarter=1).status_code == 200  # justo en el límite
    response = http.get(seeded_130.cast.alicia, year=2025, quarter=2)
    assert (response.status_code, response.json()["code"]) == (422, "quarter_too_large")
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "desde el 1 de enero" in response.json()["detail"] and "10.000" in response.json()["detail"]
    assert (
        http.get(seeded_130.cast.alicia, year=2026, quarter=1).status_code == 200
    )  # sin documentos: dentro del límite


# --- El 130 no lee las líneas de IVA ---------------------------------------------------------------------------------------------------


def test_a_corrupt_vat_rate_does_not_break_the_130(http: Http, admin: Connection[DictRow], app_pool: Pool) -> None:
    person = make_cast(admin).alicia
    bad = [{"vat_rate": "veintiuno", "base_cents": 10_000, "vat_cents": 2_100}]
    insert(
        admin,
        params(
            person, new_document(app_pool, person), date=date(2025, 5, 6), lines=bad, deductible=False, number="C-1"
        ),
    )
    assert http.get(person, url="/api/tax/303", year=2025, quarter=2).json()["code"] == "unsupported_vat_rate"
    response = http.get(person, year=2025, quarter=2)
    assert response.status_code == 200, response.text
    assert box(response.json(), "02")["amount_cents"] == 12_100  # base + IVA no deducible


# --- AC-16 · quién puede verlo -----------------------------------------------------------------------------------------------------------


def test_managers_and_admins_are_refused_even_with_an_active_link_and_there_is_no_anonymous_access(
    http: Http, app_pool: Pool, seeded_130: Seeded
) -> None:  # AC-16, T9-05
    apply_scenario(app_pool, seeded_130.cast, "active")
    for who in ("gina", "gus", "adan"):
        response = http.get(seeded_130.cast[who], year=2025, quarter=2)
        assert (response.status_code, response.json()["code"]) == (403, "forbidden"), who
    assert http.get(None, year=2025, quarter=2).status_code == 401


def test_another_user_sees_only_their_own_documents_and_an_empty_year_is_without_activity(
    http: Http, seeded_130: Seeded
) -> None:  # AC-16, AC-22, AC-23
    first = http.get(seeded_130.cast.beto, year=2025, quarter=1).json()
    assert first["result_kind"] == "sin_actividad" and first["withheld_share_percent"] is None
    assert all(b["amount_cents"] == 0 and not b["items"] for b in first["boxes"])
    second = http.get(seeded_130.cast.beto, year=2025, quarter=2).json()
    assert second["result_kind"] == "sin_actividad" and second["result_cents"] == 0
    assert [i["kind"] for b in second["boxes"] for i in b["items"]] == [
        "quarter"
    ]  # solo el pago (0) del T1, ningún documento
    assert len(first["notes"]) == len(second["notes"]) == 3  # los avisos van siempre


# --- AC-17, T9-06, T9-07 · solo lee y no cuenta nada --------------------------------------------------------------------------------------


def counts(admin: Connection[DictRow]) -> tuple[int, int, int]:
    row = admin.execute(
        "select (select count(*) from public.invoices) as i, (select count(*) from public.expenses) as e, "
        "(select count(*) from public.activity_log) as a"
    ).fetchone()
    assert row is not None
    return int(row["i"]), int(row["e"]), int(row["a"])


def test_reading_writes_nothing_and_logs_nothing_about_the_documents(
    http: Http, admin: Connection[DictRow], seeded_130: Seeded
) -> None:
    before = counts(admin)
    with captured_logs("cuadre") as records:
        for q in (1, 2, 3, 4):
            assert http.get(seeded_130.cast.alicia, year=2025, quarter=q).status_code == 200
    assert counts(admin) == before
    seen = rendered(records)
    for label in ("2025-001", "R-2025-001", "G11", "G12"):  # números de factura y proveedores sembrados
        assert label not in seen
    for amount in ("123459", "18519", "60007", "30001", "1500000"):  # importes de B.1
        assert amount not in seen


# --- AC-22 · avisos --------------------------------------------------------------------------------------------------------------------------


def test_the_fixed_notes_are_always_there(http: Http, seeded_130: Seeded) -> None:
    notes = http.get(seeded_130.cast.alicia, year=2025, quarter=1).json()["notes"]
    empty = http.get(seeded_130.cast.alicia, year=2026, quarter=1).json()["notes"]
    assert len(notes) == 3 and notes == empty
    assert "orientativo" in notes[0].lower() and "1 de enero" in notes[0]
    for what in ("5 %", "minoraciones", "vivienda afecta", "compensación", "inhábil"):
        assert what in notes[1]
    assert "70 %" in notes[2] and "informativo" in notes[2]


# --- T9-08 · cabe en una respuesta de una Vercel Function -------------------------------------------------------------------------------------


def test_the_biggest_admissible_period_fits_in_a_function_response() -> None:
    day = date(2025, 5, 10)
    # El peor caso: cada factura sale dos veces (en la 01 y en la 06, porque lleva retención).
    rows = [IncomeRow(str(uuid.uuid4()), f"2025-{n:05d}", day, 123_456, 18_518) for n in range(YEAR_MAX_DOCUMENTS)]
    size = len(present_130(build_modelo_130(2025, 2, rows, [], date(2026, 6, 1))).model_dump_json())
    assert size < 4_500_000, size
    json.loads(present_130(build_modelo_130(2025, 2, rows[:2], [], date(2026, 6, 1))).model_dump_json())


def test_the_operation_is_in_the_contract(app: FastAPI) -> None:  # noqa: F811
    operation = app.openapi()["paths"][URL]["get"]
    assert operation["operationId"] == "get_modelo_130"
    assert set(operation["responses"]) >= {"200", "401", "403", "422"}
