"""AC-11 (RF-011) · `POST /api/expenses`: un gasto sin factura, puntual y sin IVA (SPEC-W-003 §5.3, D-09).

La forma del cuerpo la valida la API (422 `validation_error` con la ubicación de cada campo, para mostrar el mensaje junto a él); la fecha
futura o fuera de rango la decide la base con el «hoy» de Madrid y sale como `invalid_expense` con su campo.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.documents.conftest import Api
from tests.expenses.support import actions, all_expenses, create

BODY: dict[str, Any] = {
    "expense_date": "2026-10-01",
    "concept": "Cuota de autónomos",
    "category": "self_employed_fee",
    "amount_cents": 29400,
}


def madrid_today(admin: Connection[DictRow]) -> date:
    found = admin.execute("select (now() at time zone 'Europe/Madrid')::date as today").fetchone()
    assert found is not None
    return found["today"]


def test_ac11_a_manual_expense_is_registered_without_vat_and_not_deductible(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    response = create(api, alicia)

    assert response.status_code == 201, response.text
    expense = response.json()
    assert expense["origin"] == "manual" and expense["document_id"] is None
    assert expense["expense_date"] == "2026-10-01" and expense["supplier_name"] == "Cuota de autónomos"
    assert expense["category"] == "self_employed_fee"
    assert (expense["base_cents"], expense["vat_cents"], expense["withholding_cents"], expense["total_cents"]) == (
        29400,
        0,
        0,
        29400,
    )
    assert expense["deductible_vat"] is False and expense["tax_breakdown"] == []
    assert expense["supplier_scope"] is None and expense["doc_type"] is None
    assert expense["supplier_tax_id"] is None and expense["invoice_number"] is None
    assert expense["suspicion_acknowledged"] is False and expense["voided_at"] is None

    assert [e["id"] for e in api.request("GET", "/api/expenses", alicia).json()["items"]] == [expense["id"]]
    assert actions(admin, alicia) == ["expense.registered"]


def test_the_concept_is_cleaned_and_its_limits_are_inclusive(api: Api) -> None:
    alicia = api.cast.alicia
    assert create(api, alicia, concept="  Cuota   de\tautónomos \n").json()["supplier_name"] == "Cuota de autónomos"
    assert create(api, alicia, concept="a" + chr(0) + "b" + chr(8203) + "c").json()["supplier_name"] == "abc"
    assert create(api, alicia, concept="x" * 200).status_code == 201
    assert create(api, alicia, amount_cents=1).status_code == 201
    assert create(api, alicia, amount_cents=10**14 - 1).status_code == 201


MISSING = [pytest.param(field, id=f"sin-{field}") for field in BODY]
BAD_FIELDS: list[tuple[str, Any]] = [
    ("concept", ""),
    ("concept", "   "),
    ("concept", "x" * 201),
    ("concept", None),
    ("concept", 5),
    ("amount_cents", 0),
    ("amount_cents", -5),
    ("amount_cents", 12.5),
    ("amount_cents", "100"),
    ("amount_cents", True),
    ("amount_cents", None),
    ("amount_cents", 10**14),
    ("category", "inventada"),
    ("category", None),
    ("category", 3),
    ("expense_date", "2026-1-5"),
    ("expense_date", "01/02/2026"),
    ("expense_date", 20261001),
    ("expense_date", "2026-10-01T10:00:00"),
    ("expense_date", "2026-02-30"),
    ("expense_date", None),
]


@pytest.mark.parametrize(("field", "value"), BAD_FIELDS, ids=[f"{f}={v!r}"[:40] for f, v in BAD_FIELDS])
def test_a_malformed_field_is_a_422_pointing_at_it_and_creates_nothing(
    api: Api, admin: Connection[DictRow], field: str, value: Any
) -> None:
    alicia = api.cast.alicia
    response = create(api, alicia, **{field: value})

    body = response.json()
    assert response.status_code == 422 and body["code"] == "validation_error", response.text
    assert f"body.{field}" in [e["loc"] for e in body["errors"]]
    assert all_expenses(admin, alicia) == []


@pytest.mark.parametrize("field", MISSING)
def test_a_missing_field_is_a_422(api: Api, admin: Connection[DictRow], field: str) -> None:
    alicia = api.cast.alicia
    body = {k: v for k, v in BODY.items() if k != field}
    response = api.request("POST", "/api/expenses", alicia, json=body)
    assert response.status_code == 422 and f"body.{field}" in [e["loc"] for e in response.json()["errors"]]
    assert all_expenses(admin, alicia) == []


def test_an_unknown_field_is_refused(api: Api) -> None:
    alicia = api.cast.alicia
    response = api.request("POST", "/api/expenses", alicia, json={**BODY, "owner_id": str(api.cast.beto.id)})
    assert response.status_code == 422 and "body.owner_id" in [e["loc"] for e in response.json()["errors"]]


def test_an_empty_body_is_a_422(api: Api) -> None:
    assert api.request("POST", "/api/expenses", api.cast.alicia).status_code == 422


def test_the_date_must_be_between_2000_and_today_in_madrid(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    today = madrid_today(admin)

    for fine in (today, today - timedelta(days=1), date(2000, 1, 1)):
        assert create(api, alicia, expense_date=fine.isoformat()).status_code == 201, fine

    for bad in (today + timedelta(days=1), today + timedelta(days=400), date(1999, 12, 31)):
        response = create(api, alicia, expense_date=bad.isoformat())
        body = response.json()
        assert response.status_code == 422 and body["code"] == "invalid_expense", (bad, response.text)
        assert body["field"] == "expense_date" and "2000" in body["detail"]
    assert len(all_expenses(admin, alicia)) == 3, "solo se crearon las tres fechas buenas"


def test_the_expense_belongs_to_the_caller_whatever_the_body_says(api: Api, admin: Connection[DictRow]) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    assert create(api, alicia).status_code == 201
    assert len(all_expenses(admin, alicia)) == 1 and all_expenses(admin, beto) == []
