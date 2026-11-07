"""AC-10, AC-12 · `Document.validation` y `Document.expense_id`: lo que el servidor calcula sobre lo guardado y la interfaz solo muestra.

La misma función (`cuadre.expenses.validation`) alimenta el documento y el registro: aquí se comprueba la forma, los avisos, la categoría
sugerida y el detalle de un documento ya registrado.
"""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from tests.documents.conftest import Api
from tests.expenses.support import (
    GOOD_REVIEW,
    confirm,
    read,
    registered,
    save,
    set_profile_tax_id,
    void,
)
from tests.support import Pool, call

LABELS = {
    "doc_type": "Tipo de documento válido",
    "required_data": "Datos obligatorios completos",
    "supplier_tax_id": "NIF del proveedor válido",
    "issue_date": "Fecha correcta y no futura",
    "currency": "Importe en euros",
    "vat_rates": "Tipos de IVA permitidos",
    "vat_amounts": "Cuota acorde al tipo de IVA",
    "total": "Base más IVA igual al total",
    "not_duplicate": "No está registrada ya",
}


def validation_of(api: Api, person: Any, document_id: Any) -> dict[str, Any]:
    body = api.get(person, document_id).json()["validation"]
    assert body is not None
    result: dict[str, Any] = body
    return result


def failed(validation: dict[str, Any]) -> list[str]:
    return [c["code"] for c in validation["checks"] if c["status"] == "failed"]


# --- la forma, estado a estado ---------------------------------------------------------------------------------------------------


def test_a_correct_reading_shows_every_check_in_its_fixed_order_with_its_label(api: Api) -> None:
    alicia = api.cast.alicia
    document = api.get(alicia, read(api, alicia)).json()

    validation = document["validation"]
    assert validation["can_register"] is True and validation["requires_acknowledgement"] is False
    assert [c["code"] for c in validation["checks"]] == list(LABELS), (
        "sin «dudosos revisados» ni «retención»: no aplican"
    )
    assert {c["code"]: c["label"] for c in validation["checks"]} == LABELS
    assert all(c["status"] == "ok" and c["detail"] is None for c in validation["checks"])
    assert validation["warnings"] == []
    assert validation["preview"] == {
        "supplier_scope": "national",
        "deductible_vat": True,
        "deductible_note": validation["preview"]["deductible_note"],
        "suggested_category": "software",
    }
    assert validation["preview"]["deductible_note"], "la deducibilidad se muestra siempre con su motivo"
    assert document["expense_id"] is None


def test_a_failing_check_names_its_reason_in_spanish(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia, "invoice_sum_mismatch")
    save(api, alicia, document_id)  # confirma la duda de la lectura

    validation = validation_of(api, alicia, document_id)
    assert validation["can_register"] is False and failed(validation) == ["total"]
    (total,) = (c for c in validation["checks"] if c["code"] == "total")
    assert total["detail"] == "Base más IVA da 145,20 € y el total indicado es 147,00 €."


def test_the_validation_is_null_where_there_is_nothing_to_check(api: Api, app_pool: Pool) -> None:
    alicia = api.cast.alicia
    uploading = api.uploaded(alicia)
    processing = api.uploaded(alicia)
    assert not call(app_pool, alicia, "mark_document_uploaded", processing).error
    for document_id in (uploading, processing):
        assert api.get(alicia, document_id).json()["validation"] is None

    api.script(AgentsError(FailureCode.unreadable, http_status=422, trace_id="trc_x"))
    unread = api.read(alicia)
    assert api.get(alicia, unread).json()["validation"] is None, "extraction_failed sin nada guardado"
    save(api, alicia, unread, **GOOD_REVIEW)
    assert validation_of(api, alicia, unread)["can_register"] is True, "rellenado a mano ya se comprueba"


def test_a_registered_document_has_no_validation_but_has_its_expense(api: Api) -> None:
    alicia = api.cast.alicia
    document_id, expense = registered(api, alicia)
    document = api.get(alicia, document_id).json()
    assert document["status"] == "registered" and document["validation"] is None
    assert document["expense_id"] == expense["id"]

    voided = void(api, alicia, expense["id"])
    assert voided.status_code == 200
    back = api.get(alicia, document_id).json()
    assert back["status"] == "review" and back["expense_id"] is None
    assert back["validation"]["can_register"] is True, "vuelve a revisión con su lectura intacta"


def test_a_registered_document_can_still_be_read_and_its_original_previewed(api: Api) -> None:
    alicia = api.cast.alicia
    document_id, _ = registered(api, alicia)
    assert api.get(alicia, document_id).status_code == 200
    preview = api.preview(alicia, document_id)
    assert preview.status_code == 200 and preview.json()["previewable"] is True


def test_the_documents_list_no_longer_has_registered_documents(api: Api) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok", "invoice_ok")
    kept, done = api.read(alicia), api.read(alicia)
    save(api, alicia, done, invoice_number="OTRA-1")
    assert confirm(api, alicia, done).status_code == 201
    listed = api.request("GET", "/api/documents", alicia).json()
    assert [d["id"] for d in listed] == [str(kept)]


# --- review sustituye a la lectura ------------------------------------------------------------------------------------------------


def test_the_review_replaces_the_reading_as_a_whole(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    assert api.save_review(alicia, document_id, {"supplier_tax_id": "B00000042"}).status_code == 200
    validation = validation_of(api, alicia, document_id)
    assert validation["can_register"] is False
    assert "required_data" in failed(validation), "lo que no está en el formulario no se completa con la lectura"


def test_saving_the_form_confirms_the_doubts(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia, "invoice_doubtful_nif")
    before = validation_of(api, alicia, document_id)
    assert failed(before) == ["doubts_reviewed", "supplier_tax_id"]
    (doubts,) = (c for c in before["checks"] if c["code"] == "doubts_reviewed")
    assert "un dato dudoso" in doubts["detail"]

    save(api, alicia, document_id)
    assert failed(validation_of(api, alicia, document_id)) == ["supplier_tax_id"]


# --- avisos y vista previa ----------------------------------------------------------------------------------------------------------


def warning_codes(validation: dict[str, Any]) -> list[str]:
    return [w["code"] for w in validation["warnings"]]


def test_recipient_mismatch_needs_both_tax_ids(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)  # destinatario 12345678Z

    assert warning_codes(validation_of(api, alicia, document_id)) == [], "sin NIF en el perfil no hay aviso"
    set_profile_tax_id(admin, alicia, "01230956L")
    assert warning_codes(validation_of(api, alicia, document_id)) == ["recipient_mismatch"]
    set_profile_tax_id(admin, alicia, "12345678Z")
    assert warning_codes(validation_of(api, alicia, document_id)) == []
    assert validation_of(api, alicia, document_id)["can_register"] is True, "un aviso nunca bloquea"


def test_a_simplified_ticket_is_deductible_only_with_the_profile_tax_id(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia, "ticket_simplified")
    set_profile_tax_id(admin, alicia, "12345678Z")
    assert validation_of(api, alicia, document_id)["preview"]["deductible_vat"] is False

    save(api, alicia, document_id, recipient_tax_id="12345678Z")
    preview = validation_of(api, alicia, document_id)["preview"]
    assert preview["deductible_vat"] is True and "tu NIF" in preview["deductible_note"]


def test_an_eu_supplier_is_accepted_with_its_warning_and_no_deductible_vat(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    save(
        api,
        alicia,
        document_id,
        supplier_tax_id="de 534.861.408",
        tax_breakdown=[{"vat_rate": "19", "base_cents": 2479, "vat_cents": 471}],
        total_cents=2950,
    )
    validation = validation_of(api, alicia, document_id)
    assert validation["can_register"] is True and warning_codes(validation) == ["eu_supplier"]
    assert validation["preview"]["supplier_scope"] == "eu" and validation["preview"]["deductible_vat"] is False

    expense = confirm(api, alicia, document_id).json()
    assert expense["supplier_tax_id"] == "DE534861408" and expense["supplier_scope"] == "eu"
    assert expense["deductible_vat"] is False


def test_a_registered_invoice_blocks_the_same_one_and_warns_about_a_similar_one(api: Api) -> None:
    """AC-08 · el duplicado duro bloquea; el blando (mismo día, total y NIF con otro número) solo avisa."""
    alicia = api.cast.alicia
    _, first = registered(api, alicia)
    api.script("invoice_ok", "invoice_ok")
    same, similar = api.read(alicia), api.read(alicia)

    duplicate = validation_of(api, alicia, same)
    assert duplicate["can_register"] is False and failed(duplicate) == ["not_duplicate"]

    save(api, alicia, similar, invoice_number="OTRO-1")
    soft = validation_of(api, alicia, similar)
    assert soft["can_register"] is True and warning_codes(soft) == ["possible_duplicate"]

    assert void(api, alicia, first["id"]).status_code == 200
    assert validation_of(api, alicia, same)["can_register"] is True, "anulado el primero, ya no está registrada"


# --- AC-12 · categoría sugerida ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("supplier", "category"),
    [
        ("Nubesoft S.L.", "software"),
        ("Imprenta Sol", "supplies"),
        ("Espacio Común", "workspace"),
        ("Papelería Arce", "supplies"),
        ("Gestoría Puerta", "advisory"),
        ("Un proveedor cualquiera", "other"),
    ],
)
def test_ac12_the_suggested_category_comes_from_the_supplier_name(api: Api, supplier: str, category: str) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    save(api, alicia, document_id, supplier_name=supplier)
    assert validation_of(api, alicia, document_id)["preview"]["suggested_category"] == category
