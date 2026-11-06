"""AC-14 · Corregir lo leído: `review` en céntimos, la lectura original intacta y formas inválidas rechazadas (SPEC-W-002 §5.1, §5.3).

La API valida la FORMA (tipos, fechas ISO, importes en céntimos enteros, longitudes), no la fiscalidad (SPEC-W-003).
"""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from tests.documents.conftest import Api, db_row

CORRECTION: dict[str, Any] = {
    "doc_type": "full_invoice",
    "supplier_name": "Imprenta Sol S.L.",
    "supplier_tax_id": "B00000075",
    "recipient_tax_id": "12345678Z",
    "invoice_number": "A-311",
    "issue_date": "2026-11-01",
    "currency": "EUR",
    "tax_breakdown": [{"vat_rate": "21", "base_cents": 12000, "vat_cents": 2520}],
    "withholding": None,
    "total_cents": 14520,
}


def reviewed(api: Api, fixture: str = "invoice_doubtful_nif") -> Any:
    api.script(fixture)
    return api.read(api.cast.alicia)


def test_ac14_the_correction_is_saved_in_cents_and_the_original_reading_does_not_change(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = reviewed(api)
    original = db_row(admin, document_id)["extraction"]
    assert original["supplier_tax_id"] is None

    saved = api.save_review(alicia, document_id, CORRECTION)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["status"] == "review" and body["review"] == CORRECTION
    assert body["extraction"]["supplier_tax_id"] is None, "la lectura original sigue igual"

    row = db_row(admin, document_id)
    assert row["extraction"] == original
    assert row["review"] == CORRECTION and isinstance(row["review"]["total_cents"], int)

    reloaded = api.get(alicia, document_id).json()  # «al recargar se ven las correcciones»
    assert reloaded["review"] == CORRECTION and reloaded["extraction"]["supplier_tax_id"] is None


def test_the_list_shows_the_corrected_values_when_there_are_some(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = reviewed(api)
    api.save_review(alicia, document_id, {**CORRECTION, "supplier_name": "Imprenta Corregida", "total_cents": 99900})
    (row,) = api.request("GET", "/api/documents", alicia).json()
    assert (row["supplier_name"], row["total_cents"], row["doubtful_count"]) == ("Imprenta Corregida", 99900, 1)


def test_saving_again_replaces_the_previous_correction(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id = reviewed(api)
    api.save_review(alicia, document_id, CORRECTION)
    api.save_review(alicia, document_id, {"supplier_name": "Solo esto"})
    stored = db_row(admin, document_id)["review"]
    assert stored["supplier_name"] == "Solo esto" and stored["total_cents"] is None and stored["tax_breakdown"] == []


def test_a_partial_draft_is_valid_and_every_key_is_stored(api: Api, admin: Connection[DictRow]) -> None:
    document_id = reviewed(api)
    assert api.save_review(api.cast.alicia, document_id, {}).status_code == 200
    assert set(db_row(admin, document_id)["review"]) == set(CORRECTION)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_cents", 12.5),
        ("total_cents", "120.00"),
        ("total_cents", "12050"),
        ("total_cents", True),
        ("total_cents", 10**14),
        ("total_cents", -(10**14)),
        ("doc_type", "invoice_of_the_year"),
        ("currency", "eur"),
        ("currency", "EURO"),
        ("issue_date", "01/11/2026"),
        ("issue_date", "2026-13-40"),
        ("issue_date", "2026-11-1"),
        ("issue_date", "2026-11-01T00:00:00"),
        ("issue_date", 1793491200),
        ("supplier_name", "x" * 201),
        ("supplier_name", 12345),
        ("supplier_tax_id", "x" * 33),
        ("recipient_tax_id", "x" * 33),
        ("invoice_number", "x" * 65),
        ("tax_breakdown", [{"vat_rate": "21", "base_cents": 1.5, "vat_cents": 0}]),
        ("tax_breakdown", [{"vat_rate": "21", "base_cents": "100", "vat_cents": 0}]),
        ("tax_breakdown", [{"vat_rate": "21,5", "base_cents": 100, "vat_cents": 21}]),
        ("tax_breakdown", [{"vat_rate": "1e2", "base_cents": 100, "vat_cents": 21}]),
        ("tax_breakdown", [{"vat_rate": "21", "base_cents": 100, "vat_cents": 21, "extra": 1}]),
        ("tax_breakdown", [{"vat_rate": "21", "base_cents": 100, "vat_cents": 21}] * 11),
        ("withholding", {"rate": "15", "amount_cents": 1.5}),
        ("withholding", {"rate": "15", "amount_cents": 100, "extra": 1}),
        ("withholding", "15%"),
    ],
    ids=lambda v: repr(v)[:40],
)
def test_ac14_an_amount_or_field_that_cannot_be_read_is_rejected_and_nothing_is_saved(
    api: Api, admin: Connection[DictRow], field: str, value: Any
) -> None:
    document_id = reviewed(api)
    response = api.save_review(api.cast.alicia, document_id, {**CORRECTION, field: value})
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "validation_error" and body["errors"], "señala qué campo falla"
    assert any(field in err["loc"] for err in body["errors"]), f"el error debe apuntar a {field}: {body['errors']}"
    assert db_row(admin, document_id)["review"] is None


@pytest.mark.parametrize(
    "body", [[], None, "texto", 5, {"campo_inventado": 1}, {"storage_path": "x/y.pdf"}, {"status": "registered"}]
)
def test_unknown_fields_and_non_objects_are_rejected(api: Api, admin: Connection[DictRow], body: Any) -> None:
    """El `review` lo escribe una persona: no se guarda nada que no esté en la forma de §5.3."""
    document_id = reviewed(api)
    response = api.save_review(api.cast.alicia, document_id, body)
    assert response.status_code == 422
    assert db_row(admin, document_id)["review"] is None


def test_texts_are_cleaned_and_stored_as_plain_text(api: Api, admin: Connection[DictRow]) -> None:
    document_id = reviewed(api)
    messy = "Acme\x00 ‮ S.L.\n  <b>bold</b>"
    response = api.save_review(
        api.cast.alicia, document_id, {"supplier_name": messy, "supplier_tax_id": "  \x07 ", "invoice_number": ""}
    )
    assert response.status_code == 200, response.text
    stored = db_row(admin, document_id)["review"]
    assert stored["supplier_name"] == "Acme S.L. <b>bold</b>", (
        "sin control, sin bidireccionales, y el HTML queda literal"
    )
    assert stored["supplier_tax_id"] is None and stored["invoice_number"] is None


def test_an_amount_with_the_largest_allowed_size_is_accepted(api: Api, admin: Connection[DictRow]) -> None:
    document_id = reviewed(api)
    biggest = 10**14 - 1
    assert (
        api.save_review(api.cast.alicia, document_id, {"total_cents": biggest, "tax_breakdown": []}).status_code == 200
    )
    assert db_row(admin, document_id)["review"]["total_cents"] == biggest
    assert api.save_review(api.cast.alicia, document_id, {"total_cents": -biggest}).status_code == 200


def test_a_failed_reading_can_be_filled_in_by_hand(api: Api) -> None:
    alicia = api.cast.alicia
    api.script(AgentsError(FailureCode.unreadable, http_status=422))
    document_id = api.read(alicia)
    saved = api.save_review(alicia, document_id, CORRECTION)
    assert saved.status_code == 200
    body = saved.json()
    assert body["status"] == "extraction_failed" and body["extraction"] is None and body["review"] == CORRECTION


def test_a_correction_to_someone_elses_document_is_404(api: Api, admin: Connection[DictRow]) -> None:
    document_id = reviewed(api)
    response = api.save_review(api.cast.beto, document_id, CORRECTION)
    assert response.status_code == 404 and response.json()["code"] == "document_not_found"
    assert db_row(admin, document_id)["review"] is None
