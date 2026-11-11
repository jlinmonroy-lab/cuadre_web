"""AC-10 a AC-17, AC-21 · `GET /api/tax/303`: el borrador del modelo 303 por HTTP, con la aplicación real y la base real (SPEC-W-008 §5.3, hito 3).

Los cinco trimestres de B.1 están sembrados con las funciones de la base (ver `conftest.py`). Aquí se piden por la API y se comprueba que el JSON dice lo
que dijo la persona a mano: las 13 casillas, el resultado, los documentos de cada casilla, el plazo, los errores y los avisos. Una lectura no escribe y
nada de lo que lee (proveedores, importes) va a los registros.
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

from cuadre.quarters.models import present
from cuadre.tax import InvoiceRow, build_modelo_303
from cuadre.tax.limits import QUARTER_MAX_DOCUMENTS
from tests.agents.support import captured_logs, rendered
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.clocks import FixedClock
from tests.invoicing.conftest import app  # noqa: F401 - fixture de otro conftest
from tests.quarters.conftest import Seeded
from tests.rls.expenses_support import insert, params
from tests.support import Person, Pool, apply_scenario, make_cast, new_document
from tests.tax.test_modelo_303_cases import CASES, EXPECTED_ITEMS

URL = "/api/tax/303"
ALL_CODES = ["01", "03", "04", "06", "07", "09", "27", "28", "29", "45", "46", "59", "120"]
CASE_IDS = [t["caso"] for t in CASES["trimestres"]]


def at(day: str) -> FixedClock:
    return FixedClock(datetime.fromisoformat(day).replace(hour=12, tzinfo=UTC))


@dataclass
class Http:
    app: FastAPI
    client: TestClient
    signer: Signer

    def get(self, person: Person | None, **query: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.signer.token(person)}"} if person is not None else {}
        return self.client.get(URL, headers=headers, params=query or None)

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


# --- AC-13, AC-17, NFR-08 · los cinco trimestres por HTTP -----------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES["trimestres"], ids=CASE_IDS)
def test_the_api_returns_the_hand_calculated_boxes_with_their_documents(http: Http, seeded: Seeded, case: dict) -> None:
    response = http.get(seeded.cast.alicia, year=case["anio"], quarter=case["trimestre"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert codes(body) == ALL_CODES
    assert {b["code"]: b["amount_cents"] for b in body["boxes"]} == case["casillas"]
    assert (body["result_kind"], body["result_cents"]) == (case["resultado"], case["casillas"]["46"])
    expected = EXPECTED_ITEMS[case["caso"]]
    for box in body["boxes"]:
        assert [seeded.from_db[i["id"]] for i in box["items"]] == expected.get(box["code"], []), box["code"]
        if box["measure"] is not None:  # NFR-08: la suma de los documentos es la casilla
            field = "base_cents" if box["measure"] == "base" else "vat_cents"
            assert sum(i[field] for i in box["items"]) == box["amount_cents"]


def test_the_shape_of_the_response_and_its_headers(http: Http, seeded: Seeded) -> None:
    response = http.get(seeded.cast.alicia, year=2025, quarter=2)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {
        "year", "quarter", "period_start", "period_end", "deadline", "deadline_status", "boxes", "result_cents", "result_kind", "notes",
    }  # fmt: skip
    assert (body["period_start"], body["period_end"], body["deadline"]) == ("2025-04-01", "2025-07-01", "2025-07-20")
    measures = {b["code"]: b["measure"] for b in body["boxes"]}
    assert measures["07"] == "base" and measures["09"] == "vat" and measures["27"] is None and measures["59"] == "base"
    derived = {b["code"]: b["components"] for b in body["boxes"] if b["components"]}
    assert derived == {"27": ["03", "06", "09"], "45": ["29"], "46": ["27", "45"]}
    groups = {b["code"]: b["group"] for b in body["boxes"]}
    assert groups == {
        "01": "devengado", "03": "devengado", "04": "devengado", "06": "devengado", "07": "devengado", "09": "devengado",
        "27": "devengado", "28": "deducible", "29": "deducible", "45": "deducible", "46": "resultado", "59": "adicional",
        "120": "adicional",
    }  # fmt: skip
    expense = next(b for b in body["boxes"] if b["code"] == "28")["items"][
        0
    ]  # EB1: un gasto de 400,00 € con 84,00 € de IVA
    assert (expense["kind"], expense["label"], expense["date"], expense["base_cents"], expense["vat_cents"]) == (
        "expense", "EB1", "2025-04-15", 40_000, 8_400,
    )  # fmt: skip
    first = body["boxes"][4]["items"][0]  # casilla 07
    assert set(first) == {"kind", "id", "label", "date", "base_cents", "vat_cents"} and first["kind"] == "invoice"
    assert uuid.UUID(first["id"]) and first["label"] == "2025-007"


# --- AC-10 · el plazo y su estado --------------------------------------------------------------------------------------------------


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
def test_the_deadline_and_its_status_follow_the_clock(
    http: Http, seeded: Seeded, today: str, year: int, quarter: int, deadline: str, status: str
) -> None:
    http.now(today)
    body = http.get(seeded.cast.alicia, year=year, quarter=quarter).json()
    assert (body["deadline"], body["deadline_status"]) == (deadline, status)


# --- Por defecto: el trimestre en curso (Madrid) ---------------------------------------------------------------------------------------


def test_without_parameters_it_is_the_current_quarter_in_madrid(http: Http, seeded: Seeded) -> None:
    http.now("2026-06-01")
    body = http.get(seeded.cast.alicia).json()
    assert (body["year"], body["quarter"]) == (2026, 2)
    assert [i["label"] for i in body["boxes"][4]["items"]] == ["2026-001"]  # X1, del 01/04/2026
    # A las 23:30 UTC del 31 de marzo ya es 1 de abril en Madrid.
    http.app.state.clock = FixedClock(datetime(2026, 3, 31, 23, 30, tzinfo=UTC))
    assert (http.get(seeded.cast.alicia).json()["year"], http.get(seeded.cast.alicia).json()["quarter"]) == (2026, 2)


def test_each_missing_parameter_defaults_on_its_own(http: Http, seeded: Seeded) -> None:
    http.now("2026-06-01")
    only_year = http.get(seeded.cast.alicia, year=2025).json()
    assert (only_year["year"], only_year["quarter"]) == (2025, 2)  # el trimestre de hoy, en ese año
    only_quarter = http.get(seeded.cast.alicia, quarter=1).json()
    assert (only_quarter["year"], only_quarter["quarter"]) == (2026, 1)


# --- AC-11, AC-12, AC-16 · errores ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "quarter"), [(2025, 5), (2025, 0), (2025, -1), (1999, 1), (9999, 1), (10**20, 1), (2025, 10**20)]
)
def test_a_period_that_does_not_exist_is_invalid_period(
    http: Http, seeded: Seeded, year: int, quarter: int
) -> None:  # AC-11
    response = http.get(seeded.cast.alicia, year=year, quarter=quarter)
    assert response.status_code == 422 and response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "invalid_period"
    assert str(year) not in response.json()["detail"]  # no repite lo que se envió


@pytest.mark.parametrize(
    "query", [{"year": "abc", "quarter": 1}, {"year": 2025, "quarter": "1.5"}, {"year": "", "quarter": 1}]
)
def test_a_value_that_is_not_an_integer_is_a_validation_error(
    http: Http, seeded: Seeded, query: dict[str, Any]
) -> None:
    response = http.get(seeded.cast.alicia, **query)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_a_quarter_that_has_not_started_is_in_the_future_and_the_current_one_is_fine(
    http: Http, seeded: Seeded
) -> None:  # AC-11
    http.now("2026-06-01")
    for year, quarter in ((2026, 3), (2026, 4), (2027, 1)):
        response = http.get(seeded.cast.alicia, year=year, quarter=quarter)
        assert (response.status_code, response.json()["code"]) == (422, "period_in_future")
    assert http.get(seeded.cast.alicia, year=2026, quarter=2).status_code == 200


def test_a_period_error_is_answered_before_anything_is_read(
    http: Http, seeded: Seeded, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise AssertionError("no se debía leer la base de datos")

    monkeypatch.setattr("cuadre.quarters.service.user_transaction", boom)
    assert http.get(seeded.cast.alicia, year=2025, quarter=7).json()["code"] == "invalid_period"
    assert http.get(seeded.cast.alicia, year=2027, quarter=1).json()["code"] == "period_in_future"


def test_a_quarter_with_too_many_documents_is_refused(
    http: Http, seeded: Seeded, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-16
    monkeypatch.setattr(
        "cuadre.tax.modelo_303.QUARTER_MAX_DOCUMENTS", 5
    )  # el primer trimestre de 2025 tiene 6 facturas
    response = http.get(seeded.cast.alicia, year=2025, quarter=1)
    assert (response.status_code, response.json()["code"]) == (422, "quarter_too_large")
    assert (
        http.get(seeded.cast.alicia, year=2025, quarter=2).json()["code"] == "quarter_too_large"
    )  # 6 facturas y 3 gastos
    assert http.get(seeded.cast.alicia, year=2026, quarter=1).status_code == 200  # sin documentos: dentro del límite


def test_a_corrupt_vat_rate_is_an_error_with_a_warning_that_carries_no_data(
    http: Http, admin: Connection[DictRow], app_pool: Pool
) -> None:  # AC-12
    person = make_cast(admin).alicia
    bad = [{"vat_rate": "veintiuno", "base_cents": 4_747_474, "vat_cents": 996_970}]
    insert(
        admin,
        params(person, new_document(app_pool, person), date=date(2025, 5, 6), name="Proveedor Reservado 5519", lines=bad,
               base=4_747_474, vat=996_970, total=5_744_444, deductible=False, number="C-1"),
    )  # fmt: skip
    with captured_logs("cuadre") as records:
        response = http.get(person, year=2025, quarter=2)
    assert (response.status_code, response.json()["code"]) == (422, "unsupported_vat_rate")
    seen = response.text + rendered(records)
    for secret in ("veintiuno", "Proveedor Reservado", "4747474", "996970", "5744444"):
        assert secret not in seen
    assert any(r.getMessage() == "modelo_303_unsupported_vat_rate" for r in records)


# --- AC-14 · quién puede verlo ----------------------------------------------------------------------------------------------------------


def test_managers_and_admins_are_refused_even_with_an_active_link_and_there_is_no_anonymous_access(
    http: Http, app_pool: Pool, seeded: Seeded
) -> None:  # AC-14, T8-05
    apply_scenario(app_pool, seeded.cast, "active")
    for who in ("gina", "gus", "adan"):
        response = http.get(seeded.cast[who], year=2025, quarter=2)
        assert (response.status_code, response.json()["code"]) == (403, "forbidden"), who
    assert http.get(None, year=2025, quarter=2).status_code == 401


def test_another_user_sees_only_their_own_documents(http: Http, seeded: Seeded) -> None:
    body = http.get(seeded.cast.beto, year=2025, quarter=2).json()
    assert body["result_kind"] == "sin_actividad" and all(
        b["amount_cents"] == 0 and not b["items"] for b in body["boxes"]
    )


# --- AC-15, T8-06, T8-07 · solo lee y no cuenta nada --------------------------------------------------------------------------------------


def counts(admin: Connection[DictRow]) -> tuple[int, int, int]:
    row = admin.execute(
        "select (select count(*) from public.invoices) as i, (select count(*) from public.expenses) as e, "
        "(select count(*) from public.activity_log) as a"
    ).fetchone()
    assert row is not None
    return int(row["i"]), int(row["e"]), int(row["a"])


def test_reading_writes_nothing_and_logs_nothing_about_the_documents(
    http: Http, admin: Connection[DictRow], seeded: Seeded
) -> None:
    before = counts(admin)
    with captured_logs("cuadre") as records:
        for q in (1, 2, 3, 4):
            assert http.get(seeded.cast.alicia, year=2025, quarter=q).status_code == 200
    assert counts(admin) == before
    seen = rendered(records)
    for label in ("2025-001", "R-2025-001", "ED1", "EB1", "ED4"):  # números de factura y proveedores sembrados
        assert label not in seen
    for amount in ("25253", "120250", "47410", "253000"):  # importes de las casillas de B.1
        assert amount not in seen


# --- AC-21 · avisos --------------------------------------------------------------------------------------------------------------------------


def test_the_fixed_notes_are_always_there_and_the_349_only_with_box_59(http: Http, seeded: Seeded) -> None:  # AC-21
    without = http.get(seeded.cast.alicia, year=2025, quarter=1).json()["notes"]
    empty = http.get(seeded.cast.alicia, year=2026, quarter=1).json()["notes"]
    with_eu = http.get(seeded.cast.alicia, year=2025, quarter=2).json()["notes"]
    assert len(without) == len(empty) == 3 and len(with_eu) == 4
    assert "orientativo" in without[0].lower() and "inhábil" in without[1] and "Canarias, Ceuta y Melilla" in without[2]
    assert "modelo 349" in with_eu[3] and without == empty == with_eu[:3]


# --- T8-08 · cabe en una respuesta de una Vercel Function -------------------------------------------------------------------------------------


def test_the_biggest_admissible_quarter_fits_in_a_function_response() -> None:
    day = date(2025, 5, 10)
    rows = [
        InvoiceRow(str(uuid.uuid4()), f"2025-{n:03d}", day, "national_vat", 21, 123_456, 25_926)
        for n in range(QUARTER_MAX_DOCUMENTS)
    ]  # type: ignore[arg-type]
    size = len(present(build_modelo_303(2025, 2, rows, [], date(2026, 6, 1))).model_dump_json())
    assert size < 4_500_000, size
    json.loads(present(build_modelo_303(2025, 2, rows[:2], [], date(2026, 6, 1))).model_dump_json())


def test_the_operation_is_in_the_contract(app: FastAPI) -> None:  # noqa: F811
    operation = app.openapi()["paths"][URL]["get"]
    assert operation["operationId"] == "get_modelo_303"
    assert set(operation["responses"]) >= {"200", "401", "403", "422"}
