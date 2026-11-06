"""US-005, RF-010, NFR-07 · `validate` de punta a punta, con los ejemplos de `contracts/examples/extract/` (SPEC-W-003 §5.1, §7)."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from cuadre.agents import normalize_extraction
from cuadre.validators import (
    CheckCode,
    ExistingExpense,
    ExpenseCategory,
    InvoiceData,
    TaxLine,
    ValidationContext,
    WarningCode,
    Withholding,
    from_stored,
    validate,
)
from tests.agents.support import example_response
from tests.validators import corpus

TODAY = date(2026, 11, 6)
OWNER_TAX_ID = "01230956L"

ORDER = [
    CheckCode.doc_type,
    CheckCode.required_data,
    CheckCode.doubts_reviewed,
    CheckCode.supplier_tax_id,
    CheckCode.issue_date,
    CheckCode.currency,
    CheckCode.vat_rates,
    CheckCode.vat_amounts,
    CheckCode.withholding,
    CheckCode.total,
    CheckCode.not_duplicate,
]
LABELS = {
    "doc_type": "Tipo de documento válido",
    "required_data": "Datos obligatorios completos",
    "doubts_reviewed": "Datos dudosos revisados",
    "supplier_tax_id": "NIF del proveedor válido",
    "issue_date": "Fecha correcta y no futura",
    "currency": "Importe en euros",
    "vat_rates": "Tipos de IVA permitidos",
    "vat_amounts": "Cuota acorde al tipo de IVA",
    "withholding": "Retención acorde a su porcentaje",
    "total": "Base más IVA igual al total",
    "not_duplicate": "No está registrada ya",
}


def stored(name: str) -> dict[str, Any]:
    """La lectura del ejemplo, normalizada exactamente como se guardaría en `documents.extraction`."""
    return normalize_extraction(example_response(name)).extraction


def context(**changes: Any) -> ValidationContext:
    return replace(ValidationContext(today=TODAY), **changes)


def codes(validation: Any, status: str) -> list[CheckCode]:
    return [c.code for c in validation.checks if c.status == status]


def good() -> InvoiceData:
    return from_stored(stored("invoice_ok"))


# --- Los ejemplos del contrato -------------------------------------------------------------------------------------------------------


def test_invoice_ok_can_be_registered() -> None:
    result = validate(from_stored(stored("invoice_ok")), context())
    assert result.can_register and codes(result, "failed") == []
    assert [c.code for c in result.checks] == [
        CheckCode.doc_type,
        CheckCode.required_data,
        CheckCode.supplier_tax_id,
        CheckCode.issue_date,
        CheckCode.currency,
        CheckCode.vat_rates,
        CheckCode.vat_amounts,
        CheckCode.total,
        CheckCode.not_duplicate,
    ]  # sin «dudosos revisados» y sin «retención»: no aplican
    assert not result.requires_acknowledgement and result.warnings == ()
    assert (result.preview.supplier_scope, result.preview.deductible_vat) == ("national", True)
    assert result.preview.suggested_category is ExpenseCategory.software  # «Nubesoft S.L.»


def test_the_values_to_register_are_normalized() -> None:
    values = validate(from_stored(stored("invoice_ok")), context()).values
    assert values is not None
    assert (values.expense_date, values.supplier_name, values.supplier_tax_id, values.supplier_scope) == (
        date(2026, 10, 28),
        "Nubesoft S.L.",
        "B00000042",
        "national",
    )
    assert (values.invoice_number, values.invoice_number_key, values.doc_type) == (
        "NS-2026-9921",
        "NS20269921",
        "full_invoice",
    )
    assert (values.base_cents, values.vat_cents, values.withholding_cents, values.total_cents) == (2479, 521, 0, 3000)
    assert values.tax_lines == (TaxLine("21", 2479, 521),) and values.deductible_vat


def test_us_005_a_sum_that_does_not_add_up_fails_only_the_total_and_blocks_the_registration() -> None:
    """120,00 de base y 25,20 de cuota dan 145,20, y la factura dice 147,00."""
    result = validate(from_stored(stored("invoice_sum_mismatch")), context())
    assert not result.can_register
    assert codes(result, "failed") == [CheckCode.total]
    total = next(c for c in result.checks if c.code is CheckCode.total)
    assert total.label == "Base más IVA igual al total"
    assert total.detail == "Base más IVA da 145,20 € y el total indicado es 147,00 €."
    assert result.values is None


def test_an_illegible_tax_id_fails_it_and_the_unreviewed_doubt() -> None:
    extraction = stored("invoice_doubtful_nif")
    doubts = len(extraction["doubtful_fields"])
    assert extraction["supplier_tax_id"] is None and doubts == 1
    result = validate(from_stored(extraction), context(doubtful_count=doubts, has_review=False))
    assert codes(result, "failed") == [CheckCode.doubts_reviewed, CheckCode.supplier_tax_id]
    by_code = {c.code: c for c in result.checks}
    assert by_code[CheckCode.supplier_tax_id].detail == "Falta el NIF del proveedor."
    assert (
        by_code[CheckCode.doubts_reviewed].detail is not None
        and "un dato dudoso" in by_code[CheckCode.doubts_reviewed].detail
    )  # type: ignore[operator]


def test_saving_the_form_confirms_the_doubts_but_the_tax_id_still_has_to_be_filled_in() -> None:
    extraction = stored("invoice_doubtful_nif")
    still_empty = validate(from_stored(extraction), context(doubtful_count=1, has_review=True))
    assert codes(still_empty, "failed") == [CheckCode.supplier_tax_id]
    review = {**extraction, "supplier_tax_id": "B00000075"}
    filled = validate(from_stored(review), context(doubtful_count=1, has_review=True))
    assert filled.can_register and CheckCode.doubts_reviewed in [c.code for c in filled.checks]


def test_hidden_instructions_never_change_a_check_they_only_require_acknowledgement() -> None:
    """NFR-07: `injection_suspected` no valida ni exime de nada."""
    data = from_stored(stored("invoice_injection"))
    quiet = validate(data, context(injection_suspected=False))
    flagged = validate(data, context(injection_suspected=True))
    assert quiet.checks == flagged.checks and quiet.warnings == flagged.warnings
    assert quiet.can_register and flagged.can_register
    assert (quiet.requires_acknowledgement, flagged.requires_acknowledgement) == (False, True)
    bad = replace(data, total_cents=999)
    assert not validate(bad, context(injection_suspected=True)).can_register


def test_a_simplified_ticket_can_be_registered_but_is_not_deductible_without_your_tax_id() -> None:
    extraction = stored("ticket_simplified")
    assert extraction["doc_type"] == "simplified_invoice" and extraction["recipient_tax_id"] is None
    result = validate(from_stored(extraction), context(owner_tax_id=OWNER_TAX_ID))
    assert result.can_register
    assert result.preview.deductible_vat is False
    assert result.preview.deductible_note == "Factura simplificada: el IVA solo se deduce si lleva tu NIF."
    with_nif = validate(
        from_stored({**extraction, "recipient_tax_id": OWNER_TAX_ID}), context(owner_tax_id=OWNER_TAX_ID)
    )
    assert with_nif.preview.deductible_vat is True and with_nif.can_register
    assert result.preview.suggested_category is ExpenseCategory.supplies  # «Papelería Arce S.L.»


# --- Orden, etiquetas y composición ---------------------------------------------------------------------------------------------------


def test_all_eleven_checks_in_their_fixed_order_with_their_labels() -> None:
    data = replace(good(), withholding=Withholding("15", 372), total_cents=3000 - 372)
    result = validate(data, context(doubtful_count=2, has_review=True))
    assert [c.code for c in result.checks] == ORDER
    labels = {c.code.value: c.label for c in result.checks}
    assert labels == {**LABELS, "total": "Base más IVA menos retención igual al total"}
    assert result.can_register


def test_the_withholding_check_only_appears_when_the_invoice_has_one_and_the_doubts_one_only_when_there_are_doubts() -> (
    None
):
    plain = [c.code for c in validate(good(), context()).checks]
    assert CheckCode.withholding not in plain and CheckCode.doubts_reviewed not in plain
    with_doubts = [c.code for c in validate(good(), context(doubtful_count=1)).checks]
    assert CheckCode.doubts_reviewed in with_doubts


@pytest.mark.parametrize(
    ("change", "failing"),
    [
        ({"doc_type": None}, CheckCode.doc_type),
        ({"doc_type": "other"}, CheckCode.doc_type),
        ({"doc_type": "not_an_invoice"}, CheckCode.doc_type),
        ({"supplier_name": None}, CheckCode.required_data),
        ({"invoice_number": None}, CheckCode.required_data),  # una factura completa necesita número
        ({"tax_lines": ()}, CheckCode.required_data),
        ({"total_cents": None}, CheckCode.required_data),
        ({"supplier_tax_id": None}, CheckCode.supplier_tax_id),
        ({"supplier_tax_id": "B00000043"}, CheckCode.supplier_tax_id),  # control equivocado
        ({"issue_date": None}, CheckCode.issue_date),
        ({"issue_date": date(2026, 11, 7)}, CheckCode.issue_date),
        ({"issue_date_malformed": True}, CheckCode.issue_date),
        ({"currency": "USD"}, CheckCode.currency),
        ({"tax_lines": (TaxLine("19", 2479, 471),), "total_cents": 2950}, CheckCode.vat_rates),
        ({"tax_lines": (TaxLine("21", 2479, 600),), "total_cents": 3079}, CheckCode.vat_amounts),
        ({"total_cents": 3002}, CheckCode.total),
    ],
)
def test_a_single_failing_check_blocks_the_registration(change: dict[str, Any], failing: CheckCode) -> None:
    result = validate(replace(good(), **change), context())
    assert not result.can_register and failing in codes(result, "failed")
    assert result.values is None
    assert all(c.status in ("ok", "failed") for c in result.checks)


def test_can_register_needs_every_check_not_just_one() -> None:
    result = validate(replace(good(), currency="USD", total_cents=3002), context())
    assert len(codes(result, "failed")) >= 2 and not result.can_register


# --- Motivos concretos --------------------------------------------------------------------------------------------------------------


def test_a_foreign_currency_points_to_the_manual_expense() -> None:
    result = validate(replace(good(), currency="USD"), context())
    detail = next(c.detail for c in result.checks if c.code is CheckCode.currency)
    assert detail is not None and "no está en euros" in detail and "gasto sin factura" in detail
    assert validate(replace(good(), currency=None), context()).can_register  # sin moneda se da por euros


def test_a_ticket_may_have_no_invoice_number_but_a_full_invoice_may_not() -> None:
    ticket = replace(good(), doc_type="ticket", invoice_number=None)
    assert validate(ticket, context()).can_register
    assert not validate(replace(good(), invoice_number=None), context()).can_register
    assert validate(replace(good(), doc_type="receipt", invoice_number=None), context()).can_register


@pytest.mark.parametrize("total", [0, -3000])
def test_a_zero_or_negative_total_is_not_registered_credit_notes_come_later(total: int) -> None:
    result = validate(replace(good(), total_cents=total), context())
    detail = next(c.detail for c in result.checks if c.code is CheckCode.required_data)
    assert detail is not None and "abonos" in detail and not result.can_register


def test_a_negative_line_is_not_registered_either() -> None:
    data = replace(good(), tax_lines=(TaxLine("21", -2479, -521),), total_cents=-3000)
    assert not validate(data, context()).can_register


def test_more_than_ten_tax_lines_are_rejected() -> None:
    data = replace(good(), tax_lines=tuple(TaxLine("21", 100, 21) for _ in range(11)), total_cents=1331)
    detail = next(c.detail for c in validate(data, context()).checks if c.code is CheckCode.required_data)
    assert detail is not None and "más de 10 líneas" in detail


def test_missing_data_makes_the_arithmetic_checks_say_they_cannot_be_checked() -> None:
    result = validate(replace(good(), tax_lines=(), total_cents=None), context())
    arithmetic = {
        c.code: c.detail
        for c in result.checks
        if c.code in (CheckCode.vat_rates, CheckCode.vat_amounts, CheckCode.total)
    }
    assert all(d is not None and d.startswith("No se puede comprobar") for d in arithmetic.values())


def test_a_withholding_is_checked_against_its_rate_and_subtracted_from_the_total() -> None:
    right = replace(good(), withholding=Withholding("15", 372), total_cents=2628)
    assert validate(right, context()).can_register
    wrong_amount = replace(right, withholding=Withholding("15", 400))
    assert codes(validate(wrong_amount, context()), "failed") == [CheckCode.withholding, CheckCode.total]
    not_subtracted = replace(right, total_cents=3000)
    assert codes(validate(not_subtracted, context()), "failed") == [CheckCode.total]
    no_amount = replace(right, withholding=Withholding("15", None))
    assert CheckCode.withholding in codes(validate(no_amount, context()), "failed")


# --- Proveedores de la UE ----------------------------------------------------------------------------------------------------------


def test_an_eu_supplier_can_be_registered_without_deductible_vat_and_with_its_warning() -> None:
    data = replace(good(), supplier_tax_id=corpus.EU_VAT["DE"], tax_lines=(TaxLine("19", 2479, 471),), total_cents=2950)
    result = validate(data, context())
    assert result.can_register
    assert (result.preview.supplier_scope, result.preview.deductible_vat) == ("eu", False)
    assert [w.code for w in result.warnings] == [WarningCode.eu_supplier]
    assert (
        result.values is not None
        and result.values.supplier_tax_id == corpus.EU_VAT["DE"]
        and not result.values.deductible_vat
    )


def test_a_german_rate_is_not_allowed_for_a_spanish_supplier() -> None:
    data = replace(good(), tax_lines=(TaxLine("19", 2479, 471),), total_cents=2950)
    assert codes(validate(data, context()), "failed") == [CheckCode.vat_rates]


def test_gr_and_el_give_the_same_stored_key() -> None:
    body = corpus.EU_VAT["EL"][2:]
    keys = set()
    for prefix in ("EL", "GR"):
        data = replace(good(), supplier_tax_id=prefix + body, tax_lines=(TaxLine("24", 2479, 595),), total_cents=3074)
        values = validate(data, context()).values
        assert values is not None
        keys.add(values.supplier_tax_id)
    assert keys == {"EL" + body}


@pytest.mark.parametrize("tax_id", [corpus.XI, corpus.EU_OSS, "GB" + corpus.XI[2:], "IM123456789"])
def test_prefixes_outside_the_whitelist_fail_with_the_not_recognized_message(tax_id: str) -> None:
    result = validate(replace(good(), supplier_tax_id=tax_id), context())
    detail = next(c.detail for c in result.checks if c.code is CheckCode.supplier_tax_id)
    assert detail is not None and "No se reconoce como NIF español ni NIF-IVA de la UE" in detail


def test_hostile_tax_ids_fail_the_check_and_never_raise() -> None:
    for family in corpus.hostile_inputs().values():
        for raw in family[:200]:
            result = validate(replace(good(), supplier_tax_id=raw), context())
            assert CheckCode.supplier_tax_id in codes(result, "failed")


# --- Duplicados y avisos ------------------------------------------------------------------------------------------------------------


def previous(**changes: Any) -> ExistingExpense:
    return replace(
        ExistingExpense(
            supplier_tax_id="B00000042",
            invoice_number_key="NS20269921",
            expense_date=date(2026, 10, 28),
            total_cents=3000,
        ),
        **changes,
    )


def test_the_same_tax_id_and_number_is_a_hard_duplicate_even_written_differently() -> None:
    data = replace(good(), invoice_number="ns 2026 9921", supplier_tax_id="ES-b00000042")
    result = validate(data, context(existing=(previous(),)))
    assert not result.can_register and codes(result, "failed") == [CheckCode.not_duplicate]
    assert result.warnings == ()  # el duplicado duro no se anuncia además como posible


def test_the_same_day_total_and_tax_id_with_another_number_is_only_a_warning() -> None:
    result = validate(good(), context(existing=(previous(invoice_number_key="OTRO"),)))
    assert result.can_register
    assert [w.code for w in result.warnings] == [WarningCode.possible_duplicate]


def test_a_voided_expense_is_simply_not_passed_in_so_it_no_longer_counts() -> None:
    assert validate(good(), context(existing=())).can_register


def test_a_ticket_without_a_number_never_has_a_hard_duplicate_but_can_have_a_possible_one() -> None:
    ticket = replace(good(), doc_type="ticket", invoice_number=None)
    result = validate(ticket, context(existing=(previous(invoice_number_key=None),)))
    assert result.can_register and [w.code for w in result.warnings] == [WarningCode.possible_duplicate]


def test_the_recipient_warning_needs_both_tax_ids_and_counts_an_unreadable_one_as_different() -> None:
    data = from_stored(stored("invoice_ok"))  # destinatario 12345678Z
    assert [w.code for w in validate(data, context(owner_tax_id=OWNER_TAX_ID)).warnings] == [
        WarningCode.recipient_mismatch
    ]
    assert validate(data, context(owner_tax_id="12345678Z")).warnings == ()
    assert validate(data, context(owner_tax_id=None)).warnings == ()
    assert validate(data, context(owner_tax_id="  ")).warnings == ()
    assert validate(replace(data, recipient_tax_id=None), context(owner_tax_id=OWNER_TAX_ID)).warnings == ()
    unreadable = replace(data, recipient_tax_id="???")
    assert [w.code for w in validate(unreadable, context(owner_tax_id=OWNER_TAX_ID)).warnings] == [
        WarningCode.recipient_mismatch
    ]


def test_a_warning_never_blocks_the_registration() -> None:
    result = validate(
        from_stored(stored("invoice_ok")),
        context(owner_tax_id=OWNER_TAX_ID, existing=(previous(invoice_number_key="X"),)),
    )
    assert len(result.warnings) == 2 and result.can_register
