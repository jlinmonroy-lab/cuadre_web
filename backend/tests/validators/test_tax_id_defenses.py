"""Defensas en profundidad de `normalize_tax_id` (Anexo B.1): lo que el prefiltro ya impide se prueba aquí sustituyendo la librería."""

import pytest

from cuadre.validators import TaxId, normalize_tax_id
from cuadre.validators import tax_id as tax_id_module
from cuadre.validators.limits import TAX_ID_KEY, TAX_ID_RAW
from tests.validators import corpus


def test_the_patterns_are_the_ones_the_database_check_and_the_spec_fix() -> None:
    """`expenses.supplier_tax_id` llevará `CHECK (supplier_tax_id ~ '^[A-Z0-9]{5,20}$')` (hito 2) y §5.1 fija el prefiltro."""
    assert TAX_ID_KEY.pattern == "[A-Z0-9]{5,20}"
    assert TAX_ID_RAW.pattern == "[0-9A-Za-z .-]{1,32}"


@pytest.mark.parametrize("returned", ["AB" + chr(10) + "1234", "12345678z", "1234", "A" * 21, "12 345 678Z", ""])
def test_a_spanish_result_that_is_not_a_clean_key_is_discarded(monkeypatch: pytest.MonkeyPatch, returned: str) -> None:
    monkeypatch.setattr(tax_id_module.es_nif, "validate", lambda body: returned)
    assert normalize_tax_id("12345678Z") is None


@pytest.mark.parametrize("returned", ["de534861408", "DE5348614" + chr(10), "DE5", "XX534861408", "DE" + "1" * 19])
def test_an_eu_result_must_keep_its_prefix_and_be_a_clean_key(monkeypatch: pytest.MonkeyPatch, returned: str) -> None:
    monkeypatch.setattr(tax_id_module.eu_vat, "validate", lambda number: returned)
    assert normalize_tax_id("DE534861408") is None


@pytest.mark.parametrize("returned", [None, 534861408, b"DE534861408"])
def test_a_library_result_that_is_not_text_is_discarded(monkeypatch: pytest.MonkeyPatch, returned: object) -> None:
    monkeypatch.setattr(tax_id_module.es_nif, "validate", lambda body: returned)
    monkeypatch.setattr(tax_id_module.eu_vat, "validate", lambda number: returned)
    assert normalize_tax_id("12345678Z") is None
    assert normalize_tax_id("DE534861408") is None


@pytest.mark.parametrize(
    "error", [ValueError, TypeError, KeyError, RuntimeError, OverflowError, UnicodeError, RecursionError]
)
def test_any_exception_from_the_library_means_not_valid(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    def boom(_: str) -> str:
        raise error("fallo de la librería")

    monkeypatch.setattr(tax_id_module.es_nif, "validate", boom)
    monkeypatch.setattr(tax_id_module.eu_vat, "validate", boom)
    assert normalize_tax_id("12345678Z") is None
    assert normalize_tax_id("ES12345678Z") is None
    assert normalize_tax_id(corpus.EU_VAT["DE"]) is None


def test_what_the_library_returns_is_what_gets_stored_when_it_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tax_id_module.es_nif, "validate", lambda body: "ABCDE12345")
    monkeypatch.setattr(tax_id_module.eu_vat, "validate", lambda number: number)
    assert normalize_tax_id("12345678Z") == TaxId("national", "ABCDE12345")
    assert normalize_tax_id("de534861408") == TaxId("eu", "DE534861408")
    assert normalize_tax_id("gr333906790") == TaxId("eu", "EL333906790")
