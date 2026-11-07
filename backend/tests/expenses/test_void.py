"""AC-13 · `POST /api/expenses/{id}/void`: anular un gasto lo saca de las cuentas, deja rastro y devuelve su documento a revisión (D-10)."""

from typing import Any
from uuid import uuid4

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from tests.documents.conftest import Api, db_row
from tests.expenses.support import (
    GOOD_REVIEW,
    actions,
    all_expenses,
    confirm,
    live_expenses,
    manual,
    read,
    registered,
    save,
    void,
)


def test_ac13_voiding_returns_the_document_to_review_and_it_can_be_registered_again(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    corrected = save(api, alicia, document_id, supplier_name="Nubesoft Corregida S.L.")["review"]
    first = confirm(api, alicia, document_id).json()
    assert first["supplier_name"] == "Nubesoft Corregida S.L."
    extraction = db_row(admin, document_id)["extraction"]

    # Mientras el gasto cuenta, el documento no se descarta ni se corrige.
    assert api.discard(alicia, document_id).status_code == 409
    blocked = api.save_review(alicia, document_id, corrected)
    assert blocked.status_code == 409 and blocked.json()["code"] == "document_wrong_state"

    response = void(api, alicia, first["id"])

    assert response.status_code == 200, response.text
    assert response.json() == {"id": first["id"], "document_id": str(document_id), "document_status": "review"}
    row = db_row(admin, document_id)
    assert row["status"] == "review" and row["review"] == corrected and row["extraction"] == extraction
    voided = api.request("GET", f"/api/expenses/{first['id']}", alicia).json()
    assert voided["voided_at"] is not None and voided["total_cents"] == first["total_cents"]
    assert api.request("GET", "/api/expenses", alicia).json()["items"] == []

    again = confirm(api, alicia, document_id)
    assert again.status_code == 201, again.text
    assert again.json()["id"] != first["id"], "el segundo es un gasto nuevo"
    assert [str(r["id"]) for r in live_expenses(admin, alicia)] == [again.json()["id"]]
    assert len(all_expenses(admin, alicia)) == 2
    assert actions(admin, alicia) == ["expense.registered", "expense.voided", "expense.registered"]


def test_voiding_twice_is_a_409_and_changes_nothing(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id, expense = registered(api, alicia)
    assert void(api, alicia, expense["id"]).status_code == 200
    rows, logged = all_expenses(admin, alicia), actions(admin, alicia)

    again = void(api, alicia, expense["id"])

    assert again.status_code == 409 and again.json()["code"] == "expense_wrong_state"
    assert all_expenses(admin, alicia) == rows and actions(admin, alicia) == logged
    assert db_row(admin, document_id)["status"] == "review"


def test_a_voided_manual_expense_does_not_come_back(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    expense = manual(api, alicia)
    response = void(api, alicia, expense["id"])
    assert response.status_code == 200
    assert response.json() == {"id": expense["id"], "document_id": None, "document_status": None}
    assert api.request("GET", "/api/expenses", alicia).json()["items"] == []
    assert api.request("GET", f"/api/expenses/{expense['id']}", alicia).json()["voided_at"] is not None


def test_a_document_that_was_never_read_goes_back_to_extraction_failed(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script(AgentsError(FailureCode.unreadable, http_status=422, trace_id="trc_x"))
    document_id = api.read(alicia)
    assert api.save_review(alicia, document_id, GOOD_REVIEW).status_code == 200
    expense = confirm(api, alicia, document_id).json()

    response = void(api, alicia, expense["id"])

    assert response.json()["document_status"] == "extraction_failed"
    shown = api.get(alicia, document_id).json()
    assert shown["status"] == "extraction_failed" and shown["extraction"] is None
    assert shown["error"]["code"] == "unreadable" and shown["review"]["total_cents"] == 12100


def test_after_voiding_the_document_can_be_discarded(api: Api) -> None:
    alicia = api.cast.alicia
    document_id, expense = registered(api, alicia)
    assert void(api, alicia, expense["id"]).status_code == 200
    assert api.discard(alicia, document_id).status_code == 204


def test_the_same_invoice_can_be_registered_again_after_voiding_the_first(api: Api) -> None:
    """AC-08 · el duplicado duro solo cuenta entre los gastos vivos."""
    alicia = api.cast.alicia
    _, first = registered(api, alicia)
    api.script("invoice_ok")
    second = api.read(alicia)
    blocked = confirm(api, alicia, second)
    assert blocked.status_code == 422 and blocked.json()["failed_checks"] == ["not_duplicate"]

    assert void(api, alicia, first["id"]).status_code == 200
    assert confirm(api, alicia, second).status_code == 201


def test_an_unknown_or_foreign_expense_is_a_404(api: Api, admin: Connection[DictRow]) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    expense = manual(api, alicia)
    for person, target in ((beto, expense["id"]), (alicia, uuid4())):
        response = void(api, person, target)
        assert response.status_code == 404 and response.json()["code"] == "expense_not_found"
    assert len(live_expenses(admin, alicia)) == 1


def test_a_malformed_id_is_a_422(api: Api) -> None:
    assert api.request("POST", "/api/expenses/no-es-un-uuid/void", api.cast.alicia).status_code == 422


def test_the_void_response_has_exactly_three_fields(api: Api) -> None:
    alicia = api.cast.alicia
    body: dict[str, Any] = void(api, alicia, manual(api, alicia)["id"]).json()
    assert set(body) == {"id", "document_id", "document_status"}
