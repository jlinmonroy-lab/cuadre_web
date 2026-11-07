"""AC-01 · Qué falta para poder emitir (US-007, D-05): nombre, NIF español válido y domicilio, por nombre y en orden."""

import pytest

from cuadre.profile import Missing, StoredIdentity, completeness

NAME = Missing("legal_name", "Nombre o razón social")
NIF = Missing("tax_id", "NIF")
ADDRESS = Missing("fiscal_address", "Domicilio fiscal")
OK = {"legal_name": "Alicia Demo", "tax_id": "12345678Z", "fiscal_address": "Calle Ficticia 1"}


def missing(**stored: object) -> tuple[Missing, ...]:
    return completeness(StoredIdentity(**stored)).missing_for_invoicing


def test_an_empty_profile_lists_the_three_fields_by_name_and_in_order() -> None:
    result = completeness(StoredIdentity())
    assert result.can_issue is False
    assert result.missing_for_invoicing == (NAME, NIF, ADDRESS)
    assert [m.label for m in result.missing_for_invoicing] == ["Nombre o razón social", "NIF", "Domicilio fiscal"]


def test_a_complete_profile_can_issue() -> None:
    result = completeness(StoredIdentity(**OK))
    assert result.can_issue is True
    assert result.missing_for_invoicing == ()


@pytest.mark.parametrize(
    ("absent", "expected"),
    [("legal_name", NAME), ("tax_id", NIF), ("fiscal_address", ADDRESS)],
)
def test_each_missing_field_is_reported_alone(absent: str, expected: Missing) -> None:
    stored = {**OK, absent: None}
    assert missing(**stored) == (expected,)
    assert completeness(StoredIdentity(**stored)).can_issue is False


def test_two_missing_fields_keep_the_order() -> None:
    assert missing(legal_name="Alicia Demo", tax_id=None, fiscal_address=None) == (NIF, ADDRESS)
    assert missing(legal_name=None, tax_id="12345678Z", fiscal_address=None) == (NAME, ADDRESS)


@pytest.mark.parametrize(
    "tax_id",
    ["TEST-0001", "TEST-ALICIA", "12345678A", "DE534861408", "FR89195505110", "", "   ", 12345678, "12345678Z\u200b"],
)
def test_a_stored_tax_id_that_is_no_longer_a_valid_spanish_one_counts_as_missing(tax_id: object) -> None:
    """El NIF del seed antiguo (`TEST-0001`) y uno extranjero no sirven para emitir."""
    assert missing(**{**OK, "tax_id": tax_id}) == (NIF,)


@pytest.mark.parametrize(
    ("field", "value"),
    [("legal_name", "A"), ("legal_name", "  "), ("fiscal_address", "Av"), ("fiscal_address", "\n"), ("legal_name", 7)],
)
def test_stored_text_that_is_too_short_or_blank_counts_as_missing(field: str, value: object) -> None:
    expected = {"legal_name": NAME, "fiscal_address": ADDRESS}[field]
    assert missing(**{**OK, field: value}) == (expected,)


def test_the_stored_values_may_have_blanks_around_them() -> None:
    assert (
        completeness(
            StoredIdentity(legal_name=" Alicia Demo ", tax_id=" 12345678z ", fiscal_address=" Calle Ficticia 1 ")
        ).can_issue
        is True
    )
