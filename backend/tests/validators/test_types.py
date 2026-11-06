"""`from_stored`: lee la forma guardada en `documents.review` y `documents.extraction` (SPEC-W-002 §5.3) tolerando lo que falte o venga mal."""

from datetime import date, datetime

import pytest

from cuadre.validators import InvoiceData, TaxLine, Withholding, from_stored

FULL = {
    "doc_type": "full_invoice",
    "supplier_name": "Nubesoft S.L.",
    "supplier_tax_id": "B00000042",
    "recipient_tax_id": "12345678Z",
    "invoice_number": "NS-2026-9921",
    "issue_date": "2026-10-28",
    "currency": "EUR",
    "tax_breakdown": [{"vat_rate": "21", "base_cents": 2479, "vat_cents": 521}],
    "withholding": {"rate": "15", "amount_cents": 372},
    "total_cents": 3000,
    "doubtful_fields": [],
    "warnings": [],
}


def test_a_complete_reading_is_read_field_by_field() -> None:
    assert from_stored(FULL) == InvoiceData(
        doc_type="full_invoice",
        supplier_name="Nubesoft S.L.",
        supplier_tax_id="B00000042",
        recipient_tax_id="12345678Z",
        invoice_number="NS-2026-9921",
        issue_date=date(2026, 10, 28),
        currency="EUR",
        tax_lines=(TaxLine("21", 2479, 521),),
        withholding=Withholding("15", 372),
        total_cents=3000,
    )


def test_an_empty_mapping_gives_an_empty_invoice() -> None:
    assert from_stored({}) == InvoiceData()


@pytest.mark.parametrize("value", [None, "", "   ", 5, True, ["x"], {"a": 1}])
def test_a_blank_or_non_text_value_is_none(value: object) -> None:
    assert from_stored({"supplier_name": value}).supplier_name is None


@pytest.mark.parametrize("value", ["1200", 1.5, True, False, None, [1]])
def test_an_amount_that_is_not_an_integer_is_none_and_a_boolean_is_not_an_integer(value: object) -> None:
    assert from_stored({"total_cents": value}).total_cents is None
    assert (
        from_stored({"tax_breakdown": [{"vat_rate": "21", "base_cents": value, "vat_cents": 1}]})
        .tax_lines[0]
        .base_cents
        is None
    )


def test_zero_and_negative_integers_are_kept() -> None:
    assert from_stored({"total_cents": 0}).total_cents == 0
    assert from_stored({"total_cents": -300}).total_cents == -300


@pytest.mark.parametrize("value", [None, "x", 5, {"vat_rate": "21"}])
def test_a_tax_breakdown_that_is_not_a_list_is_empty(value: object) -> None:
    assert from_stored({"tax_breakdown": value}).tax_lines == ()


def test_an_entry_that_is_not_an_object_counts_as_a_line_without_data() -> None:
    assert from_stored(
        {"tax_breakdown": ["x", None, {"vat_rate": "21", "base_cents": 100, "vat_cents": 21}]}
    ).tax_lines == (
        TaxLine(),
        TaxLine(),
        TaxLine("21", 100, 21),
    )


def test_withholding_keeps_what_was_read_even_if_empty() -> None:
    assert from_stored({"withholding": None}).withholding is None
    assert from_stored({"withholding": "15"}).withholding is None
    assert from_stored({"withholding": {}}).withholding == Withholding(
        None, None
    )  # la lectura dijo que hay retención y no la entendió
    assert from_stored({"withholding": {"rate": "15"}}).withholding == Withholding("15", None)


@pytest.mark.parametrize(
    ("value", "parsed", "malformed"),
    [
        ("2026-11-01", date(2026, 11, 1), False),
        (date(2026, 11, 1), date(2026, 11, 1), False),
        (None, None, False),
        ("", None, False),
        ("2026-02-30", None, True),
        ("2026/11/01", None, True),
        ("1/1/2026", None, True),
        (20261101, None, True),
        (datetime(2026, 11, 1, 12, 0), None, True),  # una marca de tiempo no es una fecha
        ("２０２６-11-01", None, True),
    ],
)
def test_dates(value: object, parsed: date | None, malformed: bool) -> None:
    data = from_stored({"issue_date": value})
    assert (data.issue_date, data.issue_date_malformed) == (parsed, malformed)


def test_extra_keys_are_ignored_and_the_input_is_not_modified() -> None:
    shown = {**FULL, "doubtful_fields": [{"field": "total"}], "unknown": 1}
    before = repr(shown)
    from_stored(shown)
    assert repr(shown) == before
