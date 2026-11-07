"""AC-12 · `PUT /api/expenses/{id}/category` y las ocho categorías del contrato (SPEC-W-003 §5.3, D-08)."""

from typing import Any
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.validators import ExpenseCategory
from tests.documents.conftest import Api
from tests.expenses.support import actions, create, manual, registered, void


def set_category(api: Api, person: Any, expense_id: Any, category: Any) -> Any:
    return api.request("PUT", f"/api/expenses/{expense_id}/category", person, json={"category": category})


def test_ac12_changing_the_category_updates_it_and_is_logged_once(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    _, expense = registered(api, alicia, category="software")

    changed = set_category(api, alicia, expense["id"], "training")
    assert changed.status_code == 200, changed.text
    assert changed.json()["category"] == "training"
    assert {k: v for k, v in changed.json().items() if k != "category"} == {
        k: v for k, v in expense.items() if k != "category"
    }

    same = set_category(api, alicia, expense["id"], "training")
    assert same.status_code == 200 and same.json() == changed.json()
    assert actions(admin, alicia) == ["expense.registered", "expense.category_changed"], (
        "cambiar a la misma no registra nada"
    )


def test_the_category_of_a_manual_expense_can_change_too(api: Api) -> None:
    alicia = api.cast.alicia
    expense = manual(api, alicia)
    assert set_category(api, alicia, expense["id"], "other").json()["category"] == "other"


def test_a_voided_expense_keeps_its_category(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    expense = manual(api, alicia)
    assert void(api, alicia, expense["id"]).status_code == 200

    response = set_category(api, alicia, expense["id"], "other")
    assert response.status_code == 409 and response.json()["code"] == "expense_wrong_state"
    assert api.request("GET", f"/api/expenses/{expense['id']}", alicia).json()["category"] == "self_employed_fee"


def test_an_unknown_or_foreign_expense_is_a_404(api: Api) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    expense = manual(api, alicia)
    for person, target in ((beto, expense["id"]), (alicia, uuid4())):
        response = set_category(api, person, target, "other")
        assert response.status_code == 404 and response.json()["code"] == "expense_not_found"
    assert api.request("GET", f"/api/expenses/{expense['id']}", alicia).json()["category"] == "self_employed_fee"


@pytest.mark.parametrize("body", [{}, {"category": "inventada"}, {"category": None}, {"category": "other", "extra": 1}])
def test_a_malformed_body_is_a_422(api: Api, body: dict[str, Any]) -> None:
    alicia = api.cast.alicia
    expense = manual(api, alicia)
    response = api.request("PUT", f"/api/expenses/{expense['id']}/category", alicia, json=body)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_a_malformed_id_is_a_422(api: Api) -> None:
    response = api.request("PUT", "/api/expenses/no-es-un-uuid/category", api.cast.alicia, json={"category": "other"})
    assert response.status_code == 422


def test_ac12_the_openapi_enum_is_exactly_the_eight_categories_in_order(api: Api) -> None:
    schemas = api.app.openapi()["components"]["schemas"]
    assert schemas["ExpenseCategory"]["enum"] == [c.value for c in ExpenseCategory]
    assert len(schemas["ExpenseCategory"]["enum"]) == 8
    for name in ("ConfirmRequest", "SetCategory", "CreateExpense", "ExpenseSummary", "Expense"):
        assert schemas[name]["properties"]["category"]["$ref"] == "#/components/schemas/ExpenseCategory", name


def test_every_category_is_accepted_by_the_manual_expense(api: Api) -> None:
    alicia = api.cast.alicia
    for category in ExpenseCategory:
        assert create(api, alicia, category=category.value).status_code == 201, category
