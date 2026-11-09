"""AC-01 a AC-08 · El perfil por la API: vacío, completo, validación todo o nada, normalización, decimales y régimen."""

import pytest

from tests.profile.conftest import ADDRESS, IBAN, NAME, NIF, VALID, Api


def test_ac01_an_empty_profile_lists_what_is_missing_in_order(api: Api) -> None:
    body = api.profile(api.cast.alicia).json()
    assert body["completeness"]["can_issue"] is False
    assert [m["label"] for m in body["completeness"]["missing_for_invoicing"]] == [
        "Nombre o razón social",
        "NIF",
        "Domicilio fiscal",
    ]
    assert body["vat_regime"] == "general"
    assert body["has_logo"] is False


def test_ac02_saving_a_valid_profile_normalizes_and_completes(api: Api) -> None:
    response = api.save(api.cast.alicia, legal_name=f"  {NAME} ", tax_id="12345678z", fiscal_address=ADDRESS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tax_id"] == NIF
    assert body["legal_name"] == NAME
    assert body["completeness"] == {"can_issue": True, "missing_for_invoicing": []}
    assert api.profile(api.cast.alicia).json()["tax_id"] == NIF


def test_ac03_an_invalid_nif_is_a_422_with_every_error_and_saves_nothing(api: Api) -> None:
    response = api.save(api.cast.alicia, legal_name=NAME, tax_id="12345678A", fiscal_address="x", iban="ES00")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_profile"
    assert [f["field"] for f in body["fields"]] == ["tax_id", "fiscal_address", "iban"]
    assert "12345678A" not in response.text
    assert api.profile(api.cast.alicia).json()["legal_name"] is None  # ni el nombre, que era válido


def test_ac03_a_foreign_vat_number_is_not_a_spanish_nif(api: Api) -> None:
    response = api.save(api.cast.alicia, **{**VALID, "tax_id": "FR40303265045"})
    assert response.status_code == 422
    assert response.json()["fields"] == [{"field": "tax_id", "message": "Escribe un NIF, NIE o CIF español."}]


@pytest.mark.parametrize(("rate", "ok"), [("7.00", True), ("15.00", True), ("7", True), (None, True), ("10.00", False)])
def test_ac05_only_7_or_15(api: Api, rate: str | None, ok: bool) -> None:
    response = api.save(api.cast.alicia, **VALID, irpf_rate=rate)
    assert (response.status_code == 200) is ok
    if ok:
        assert response.json()["irpf_rate"] == (None if rate is None else f"{int(rate.split('.')[0])}.00")
    else:
        assert response.json()["fields"][0]["field"] == "irpf_rate"


def test_ac05_a_json_number_is_a_shape_error_not_a_float(api: Api) -> None:
    response = api.save(api.cast.alicia, **VALID, irpf_rate=7)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_ac06_the_iban_is_stored_normalized(api: Api) -> None:
    response = api.save(api.cast.alicia, **VALID, iban="es91 2100 0418 4502 0005 1332")
    assert response.status_code == 200
    assert response.json()["iban"] == IBAN
    bad = api.save(api.cast.alicia, **VALID, iban="ES91 2100 0418 4502 0005 1333")
    assert bad.status_code == 422
    assert bad.json()["fields"] == [
        {"field": "iban", "message": "El IBAN no es válido: revisa los dígitos de control."}
    ]
    assert "1333" not in bad.text
    assert api.profile(api.cast.alicia).json()["iban"] == IBAN  # el rechazo no tocó lo guardado


@pytest.mark.parametrize(("raw", "expected"), [("30.00", "30.00"), ("30", "30.00"), ("100", "100.00")])
def test_ac07_home_percentage_is_a_decimal_string(api: Api, raw: str, expected: str) -> None:
    response = api.save(api.cast.alicia, **VALID, home_pct=raw)
    assert response.status_code == 200
    assert response.json()["home_pct"] == expected


@pytest.mark.parametrize("raw", ["100.01", "-1", "abc", "1e1", chr(0x663) + chr(0x660)])
def test_ac07_home_percentage_rejects_the_rest(api: Api, raw: str) -> None:
    assert api.save(api.cast.alicia, **VALID, home_pct=raw).status_code == 422


def test_ac08_only_the_general_vat_regime(api: Api) -> None:
    assert api.save(api.cast.alicia, **VALID, vat_regime="general").status_code == 200
    response = api.save(api.cast.alicia, **VALID, vat_regime="recargo")
    assert response.status_code == 422
    assert response.json()["fields"][0]["field"] == "vat_regime"


def test_unknown_fields_are_rejected(api: Api) -> None:
    assert api.save(api.cast.alicia, **VALID, logo_path="x/y.png").status_code == 422


def test_ac04_retention_suggestion_and_warning_with_a_fixed_clock(api: Api) -> None:
    ok = api.save(api.cast.alicia, **VALID, activity_start_date="2026-03-01", irpf_rate="7.00").json()
    assert ok["retention"] == {"suggested_rate": "7.00", "reduced_until_year": 2028, "warning": None}
    late = api.save(api.cast.alicia, **VALID, activity_start_date="2023-12-31", irpf_rate="7.00").json()
    assert late["retention"]["suggested_rate"] == "15.00"
    assert late["retention"]["reduced_until_year"] == 2025
    assert late["retention"]["warning"] is not None
    fifteen = api.save(api.cast.alicia, **VALID, activity_start_date="2023-12-31", irpf_rate="15.00").json()
    assert fifteen["retention"]["warning"] is None
    none = api.save(api.cast.alicia, **VALID).json()
    assert none["retention"] == {"suggested_rate": None, "reduced_until_year": None, "warning": None}
