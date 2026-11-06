"""Los valores ya normalizados que recibirá `app.register_expense_from_document` (SPEC-W-003 §5.1, §5.4)."""

from dataclasses import replace
from datetime import date

from cuadre.validators import InvoiceData, TaxLine, ValidationContext, Withholding, validate

CONTEXT = ValidationContext(today=date(2026, 11, 6))

TWO_LINES_WITH_WITHHOLDING = InvoiceData(
    doc_type="full_invoice",
    supplier_name="  Nubesoft S.L.  ",
    supplier_tax_id="ES b00000042",
    recipient_tax_id="12345678Z",
    invoice_number="NS-2026/9921",
    issue_date=date(2026, 10, 28),
    currency="EUR",
    tax_lines=(TaxLine("21", 2479, 521), TaxLine("10", 1000, 100)),
    withholding=Withholding("15", 522),  # el 15 % de 34,79 € son 5,22 €
    total_cents=3479 + 621 - 522,
)


def test_the_values_add_every_line_carry_the_withholding_and_strip_the_name() -> None:
    result = validate(TWO_LINES_WITH_WITHHOLDING, CONTEXT)
    assert result.can_register, [c for c in result.checks if not c.ok]
    values = result.values
    assert values is not None
    assert values.supplier_name == "Nubesoft S.L."
    assert (values.base_cents, values.vat_cents, values.withholding_cents, values.total_cents) == (3479, 621, 522, 3578)
    assert values.tax_lines == TWO_LINES_WITH_WITHHOLDING.tax_lines
    assert (values.supplier_tax_id, values.supplier_scope) == ("B00000042", "national")
    assert (values.invoice_number, values.invoice_number_key) == ("NS-2026/9921", "NS20269921")
    assert (values.expense_date, values.doc_type, values.deductible_vat) == (date(2026, 10, 28), "full_invoice", True)


def test_without_withholding_the_withheld_amount_is_zero() -> None:
    data = replace(TWO_LINES_WITH_WITHHOLDING, withholding=None, total_cents=3479 + 621)
    values = validate(data, CONTEXT).values
    assert values is not None and values.withholding_cents == 0 and values.total_cents == 4100


def test_a_ticket_without_a_number_has_no_number_key() -> None:
    data = replace(
        TWO_LINES_WITH_WITHHOLDING, doc_type="ticket", invoice_number=None, withholding=None, total_cents=4100
    )
    values = validate(data, CONTEXT).values
    assert values is not None and values.invoice_number is None and values.invoice_number_key is None


def test_an_eu_supplier_is_registered_with_its_prefix_scope_and_no_deductible_vat() -> None:
    data = replace(
        TWO_LINES_WITH_WITHHOLDING,
        supplier_tax_id="de 534.861.408",
        tax_lines=(TaxLine("19", 2479, 471),),
        withholding=None,
        total_cents=2950,
    )
    values = validate(data, CONTEXT).values
    assert values is not None
    assert (values.supplier_tax_id, values.supplier_scope, values.deductible_vat) == ("DE534861408", "eu", False)
