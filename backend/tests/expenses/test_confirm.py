"""AC-01, AC-02, AC-09, AC-10 · `POST /api/documents/{id}/confirm`: comprobar lo guardado y, solo si todo pasa, registrar el gasto (SPEC-W-003 §5.3).

Se recorre el flujo REAL: subida, lectura por el agente simulado con los ejemplos de `contracts/examples/extract/`, corrección en el
formulario y confirmación. La base la comprueba el administrador de la base de datos (solo para mirar).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from tests.clocks import FixedClock
from tests.documents.conftest import Api, db_row
from tests.expenses.support import (
    GOOD_REVIEW,
    actions,
    all_expenses,
    confirm,
    live_expenses,
    read,
    registered,
    save,
)
from tests.support import Pool, call

# --- AC-02 · una factura correcta ------------------------------------------------------------------------------------------------


def test_ac02_a_correct_invoice_is_registered_with_everything_normalized(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    extraction_rate = api.get(alicia, document_id).json()["extraction"]["tax_breakdown"][0]["vat_rate"]

    response = confirm(api, alicia, document_id, category="advisory")

    assert response.status_code == 201, response.text
    expense = response.json()
    assert expense["origin"] == "document" and expense["document_id"] == str(document_id)
    assert expense["category"] == "advisory" and expense["doc_type"] == "full_invoice"
    assert (expense["supplier_name"], expense["supplier_tax_id"], expense["invoice_number"]) == (
        "Nubesoft S.L.",
        "B00000042",
        "NS-2026-9921",
    )
    assert expense["expense_date"] == "2026-10-28" and expense["supplier_scope"] == "national"
    assert (expense["base_cents"], expense["vat_cents"], expense["withholding_cents"], expense["total_cents"]) == (
        2479,
        521,
        0,
        3000,
    )
    assert expense["tax_breakdown"] == [{"vat_rate": extraction_rate, "base_cents": 2479, "vat_cents": 521}]
    assert expense["deductible_vat"] is True and expense["suspicion_acknowledged"] is False
    assert expense["voided_at"] is None and "owner_id" not in expense

    (row,) = live_expenses(admin, alicia)
    assert str(row["id"]) == expense["id"] and row["invoice_number_key"] == "NS20269921"
    assert db_row(admin, document_id)["status"] == "registered"
    assert actions(admin, alicia) == ["expense.registered"]


def test_ac02_the_registered_document_leaves_the_documents_list_and_shows_its_expense(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    expense = confirm(api, alicia, document_id).json()

    assert api.request("GET", "/api/documents", alicia).json() == []
    document = api.get(alicia, document_id).json()
    assert document["status"] == "registered" and document["expense_id"] == expense["id"]
    assert document["validation"] is None
    page = api.request("GET", "/api/expenses", alicia).json()
    assert [item["id"] for item in page["items"]] == [expense["id"]]


@pytest.mark.parametrize(
    "category", ["software", "workspace", "supplies", "utilities", "advisory", "self_employed_fee", "training", "other"]
)
def test_each_of_the_eight_categories_can_be_chosen(api: Api, category: str) -> None:
    alicia = api.cast.alicia
    response = confirm(api, alicia, read(api, alicia), category=category)
    assert response.status_code == 201 and response.json()["category"] == category


def test_a_simplified_ticket_is_registered_but_its_vat_is_not_deductible(api: Api) -> None:
    alicia = api.cast.alicia
    response = confirm(api, alicia, read(api, alicia, "ticket_simplified"), category="supplies")
    assert response.status_code == 201, response.text
    expense = response.json()
    assert expense["doc_type"] == "simplified_invoice" and expense["deductible_vat"] is False
    assert (expense["base_cents"], expense["vat_cents"], expense["total_cents"]) == (3305, 694, 3999)


# --- AC-01 · la suma que no cuadra -----------------------------------------------------------------------------------------------


def test_ac01_a_sum_that_does_not_add_up_is_refused_and_nothing_is_registered(
    api: Api, admin: Connection[DictRow]
) -> None:
    """120,00 de base y 25,20 de cuota dan 145,20, y la factura dice 147,00. Este ejemplo trae además una duda de la lectura."""
    alicia = api.cast.alicia
    document_id = read(api, alicia, "invoice_sum_mismatch")

    unsaved = confirm(api, alicia, document_id)
    assert unsaved.status_code == 422 and unsaved.json()["code"] == "validation_failed"
    assert unsaved.json()["failed_checks"] == ["doubts_reviewed", "total"]

    save(api, alicia, document_id)  # guardar el formulario, sin cambios, confirma las dudas (AC-10)
    saved = confirm(api, alicia, document_id)
    body = saved.json()
    assert saved.status_code == 422 and body["code"] == "validation_failed"
    assert body["failed_checks"] == ["total"], body
    assert body["title"] and body["detail"] and body["request_id"]
    assert "145,20" not in saved.text and "147,00" not in saved.text, "el problema no repite datos del documento"

    assert all_expenses(admin, alicia) == [] and db_row(admin, document_id)["status"] == "review"
    assert actions(admin, alicia) == []
    shown = api.get(alicia, document_id).json()["validation"]
    assert shown["can_register"] is False
    assert [c["code"] for c in shown["checks"] if c["status"] == "failed"] == ["total"]


@pytest.mark.parametrize(
    ("changes", "failed"),
    [
        ({"supplier_tax_id": "B00000043"}, ["supplier_tax_id"]),  # control equivocado
        ({"supplier_tax_id": None}, ["supplier_tax_id"]),
        ({"doc_type": "other"}, ["doc_type"]),
        ({"doc_type": None}, ["doc_type"]),
        ({"currency": "USD"}, ["currency"]),
        ({"issue_date": "2999-01-01"}, ["issue_date"]),
        ({"issue_date": None}, ["issue_date"]),
        ({"total_cents": 12102}, ["total"]),
        ({"total_cents": 0, "tax_breakdown": []}, ["required_data", "vat_rates", "vat_amounts", "total"]),
        (
            {"tax_breakdown": [{"vat_rate": "19", "base_cents": 10000, "vat_cents": 1900}], "total_cents": 11900},
            ["vat_rates"],
        ),
        (
            {"tax_breakdown": [{"vat_rate": "21", "base_cents": 10000, "vat_cents": 2500}], "total_cents": 12500},
            ["vat_amounts"],
        ),
        ({"invoice_number": None}, ["required_data"]),
        ({"supplier_name": None}, ["required_data"]),
    ],
)
def test_each_failing_check_blocks_the_registration_and_is_named(
    api: Api, admin: Connection[DictRow], changes: dict[str, Any], failed: list[str]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    save(api, alicia, document_id, **{**GOOD_REVIEW, **changes})

    response = confirm(api, alicia, document_id)

    assert response.status_code == 422 and response.json()["code"] == "validation_failed", response.text
    assert response.json()["failed_checks"] == failed
    assert all_expenses(admin, alicia) == []


# --- AC-10 · dudas ---------------------------------------------------------------------------------------------------------------


def test_ac10_an_illegible_tax_id_blocks_until_it_is_filled_in_and_the_form_saved(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia, "invoice_doubtful_nif")

    assert confirm(api, alicia, document_id).json()["failed_checks"] == ["doubts_reviewed", "supplier_tax_id"]
    save(api, alicia, document_id)  # sin cambios: confirma las dudas, pero el NIF sigue vacío
    assert confirm(api, alicia, document_id).json()["failed_checks"] == ["supplier_tax_id"]

    save(api, alicia, document_id, supplier_tax_id="B00000075")
    response = confirm(api, alicia, document_id)
    assert response.status_code == 201, response.text
    assert response.json()["supplier_tax_id"] == "B00000075" and response.json()["invoice_number"] == "A-311"


# --- AC-09 · instrucciones ocultas -----------------------------------------------------------------------------------------------


def test_ac09_a_suspicious_document_needs_the_acknowledgement_and_the_mark_is_kept(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia, "invoice_injection")
    shown = api.get(alicia, document_id).json()["validation"]
    assert shown["requires_acknowledgement"] is True and shown["can_register"] is True

    for acknowledge in (None, False):
        refused = confirm(api, alicia, document_id, acknowledge=acknowledge)
        assert refused.status_code == 422 and refused.json()["code"] == "suspicion_not_acknowledged"
    assert all_expenses(admin, alicia) == [] and db_row(admin, document_id)["status"] == "review"

    accepted = confirm(api, alicia, document_id, acknowledge=True)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["suspicion_acknowledged"] is True


def test_ac09_the_suspicion_never_validates_nor_exempts_a_failing_check(api: Api, admin: Connection[DictRow]) -> None:
    """NFR-07 · reconocerla no arregla una suma que no cuadra, y los fallos se anuncian antes que la falta de reconocimiento."""
    alicia = api.cast.alicia
    document_id = read(api, alicia, "invoice_injection")
    save(api, alicia, document_id, total_cents=9999)

    for acknowledge in (False, True):
        refused = confirm(api, alicia, document_id, acknowledge=acknowledge)
        assert refused.status_code == 422 and refused.json()["code"] == "validation_failed"
        assert refused.json()["failed_checks"] == ["total"]
    assert all_expenses(admin, alicia) == []


def test_acknowledging_something_nobody_suspected_leaves_no_mark(api: Api) -> None:
    alicia = api.cast.alicia
    response = confirm(api, alicia, read(api, alicia), acknowledge=True)
    assert response.status_code == 201 and response.json()["suspicion_acknowledged"] is False


# --- D-11 · un documento que no se pudo leer y se rellena a mano ---------------------------------------------------------------


def test_d11_a_document_that_failed_to_read_can_be_filled_in_by_hand_and_registered(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.script(AgentsError(FailureCode.unreadable, http_status=422, trace_id="trc_x"))
    document_id = api.read(alicia)
    assert api.get(alicia, document_id).json()["status"] == "extraction_failed"
    assert api.get(alicia, document_id).json()["validation"] is None, "no hay nada guardado que comprobar"

    empty = confirm(api, alicia, document_id)
    assert empty.status_code == 422 and empty.json()["code"] == "validation_failed"
    assert "required_data" in empty.json()["failed_checks"]
    assert all_expenses(admin, alicia) == []

    assert api.save_review(alicia, document_id, GOOD_REVIEW).status_code == 200
    filled = api.get(alicia, document_id).json()["validation"]
    assert filled["can_register"] is True

    response = confirm(api, alicia, document_id)
    assert response.status_code == 201, response.text
    assert response.json()["total_cents"] == 12100 and response.json()["supplier_name"] == "Proveedor Sintético SL"
    assert db_row(admin, document_id)["status"] == "registered"


# --- estados, dueños y forma del cuerpo -----------------------------------------------------------------------------------------


def test_registering_twice_is_a_conflict_and_leaves_one_expense(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id, first = registered(api, alicia)
    again = confirm(api, alicia, document_id)
    assert again.status_code == 409 and again.json()["code"] == "document_wrong_state"
    assert [str(row["id"]) for row in live_expenses(admin, alicia)] == [first["id"]]


def test_documents_that_are_not_ready_are_a_conflict_and_discarded_ones_do_not_exist(api: Api, app_pool: Pool) -> None:
    alicia = api.cast.alicia
    uploading = api.uploaded(alicia)
    processing = api.uploaded(alicia)
    assert not call(app_pool, alicia, "mark_document_uploaded", processing).error
    for document_id in (uploading, processing):
        response = confirm(api, alicia, document_id)
        assert response.status_code == 409 and response.json()["code"] == "document_wrong_state", document_id

    discarded = read(api, alicia)
    assert api.discard(alicia, discarded).status_code == 204
    gone = confirm(api, alicia, discarded)
    assert gone.status_code == 404 and gone.json()["code"] == "document_not_found"


def test_a_foreign_or_unknown_document_is_a_404(api: Api, admin: Connection[DictRow]) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    document_id = read(api, alicia)
    for target in (document_id, uuid4()):
        response = confirm(api, beto, target)
        assert response.status_code == 404 and response.json()["code"] == "document_not_found"
    assert all_expenses(admin, alicia) == [] and all_expenses(admin, beto) == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"category": "inventada"},
        {"category": None},
        {"category": "software", "acknowledge_suspicion": "yes"},
        {"category": "software", "acknowledge_suspicion": 1},
        {"category": "software", "extra": 1},
        {"acknowledge_suspicion": True},
    ],
)
def test_a_malformed_body_is_a_422_and_registers_nothing(
    api: Api, admin: Connection[DictRow], body: dict[str, Any]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    response = api.request("POST", f"/api/documents/{document_id}/confirm", alicia, json=body)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
    assert all_expenses(admin, alicia) == []


def test_without_a_body_it_is_a_422(api: Api) -> None:
    alicia = api.cast.alicia
    response = api.request("POST", f"/api/documents/{read(api, alicia)}/confirm", alicia)
    assert response.status_code == 422


# --- «hoy» es el de Madrid -----------------------------------------------------------------------------------------------------


def test_today_is_the_one_in_madrid_not_in_utc(api: Api) -> None:
    """La factura es del 28 de octubre: a las 23:30 UTC del 27 ya es 28 en Madrid, y a las 22:30 UTC todavía no."""
    alicia = api.cast.alicia
    document_id = read(api, alicia)

    api.app.state.clock = FixedClock(datetime(2026, 10, 27, 22, 30, tzinfo=UTC))
    early = confirm(api, alicia, document_id)
    assert early.status_code == 422 and early.json()["failed_checks"] == ["issue_date"]

    api.app.state.clock = FixedClock(datetime(2026, 10, 27, 23, 30, tzinfo=UTC))
    assert confirm(api, alicia, document_id).status_code == 201
