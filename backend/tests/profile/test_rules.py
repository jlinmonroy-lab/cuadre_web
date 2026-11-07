"""AC-02 a AC-08 · Validar el perfil campo a campo y todo a la vez (SPEC-W-005 §5.1)."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from cuadre.profile import ProfileValues, RawProfile, format_rate, validate_profile
from cuadre.profile.rules import MESSAGES, one_year_after
from tests.validators import corpus, corpus_iban

TODAY = date(2026, 11, 7)
GOOD = {
    "legal_name": "Alicia Demo (sintético)",
    "tax_id": "12345678z",
    "fiscal_address": "Calle Ficticia 1, 00000 Ciudad de Pruebas",
}


def check(**fields: object):  # noqa: ANN201
    return validate_profile(RawProfile(**fields), TODAY)


def error_for(field: str, value: object) -> str | None:
    """El mensaje de error del campo, o `None` si el valor se acepta (los demás campos van vacíos, que es válido)."""
    result = check(**{field: value})
    messages = {e.field: e.message for e in result.errors}
    assert set(messages) <= {field}, messages
    return messages.get(field)


def value_of(field: str, value: object) -> object:
    result = check(**{field: value})
    assert result.values is not None, result.errors
    return getattr(result.values, field)


def test_a_complete_profile_is_saved_normalized() -> None:
    result = check(
        **GOOD,
        activity="Diseño gráfico",
        iae_epigraph="844.1",
        activity_start_date=date(2025, 1, 15),
        vat_regime="general",
        irpf_rate="7",
        home_pct="30.5",
        iban="es36 0000 0000 0500 0000 0001",
    )
    assert result.errors == ()
    assert result.values == ProfileValues(
        legal_name="Alicia Demo (sintético)",
        tax_id="12345678Z",
        fiscal_address="Calle Ficticia 1, 00000 Ciudad de Pruebas",
        activity="Diseño gráfico",
        iae_epigraph="844.1",
        activity_start_date=date(2025, 1, 15),
        vat_regime="general",
        irpf_rate=Decimal("7.00"),
        home_pct=Decimal("30.50"),
        iban=corpus_iban.SEED_ALICIA,
    )


def test_an_empty_profile_is_valid_and_all_blank() -> None:
    """El perfil se puede guardar incompleto: lo que falta para emitir lo dice `completeness`."""
    for raw in (RawProfile(), RawProfile(legal_name="", tax_id="  ", fiscal_address="\n", activity="\t", iban="   ")):
        result = validate_profile(raw, TODAY)
        assert result.errors == ()
        assert result.values == ProfileValues(None, None, None, None, None, None, "general", None, None, None)


def test_values_and_errors_are_never_both() -> None:
    ok = check(**GOOD)
    assert ok.values is not None and ok.errors == ()
    bad = check(**GOOD, iban="no")
    assert bad.values is None and bad.errors != ()


def test_every_failing_field_is_reported_at_once_and_in_screen_order() -> None:
    result = check(
        legal_name="x",
        tax_id="12345678A",
        fiscal_address="a",
        activity="a" * 201,
        iae_epigraph="<b>",
        activity_start_date=date(1949, 12, 31),
        vat_regime="recargo",
        irpf_rate="10",
        home_pct="101",
        iban="ES00",
    )
    assert [e.field for e in result.errors] == [
        "legal_name",
        "tax_id",
        "fiscal_address",
        "activity",
        "iae_epigraph",
        "activity_start_date",
        "vat_regime",
        "irpf_rate",
        "home_pct",
        "iban",
    ]
    assert result.values is None


def test_one_bad_field_does_not_hide_the_valid_ones_and_nothing_is_saved() -> None:
    result = check(**GOOD, iban="ES00")
    assert [e.field for e in result.errors] == ["iban"]
    assert result.values is None  # no se guarda ningún campo, aunque los demás fueran válidos


# --- Texto --------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "short", "long", "low", "high"),
    [
        ("legal_name", "legal_name", "legal_name_long", 2, 200),
        ("fiscal_address", "fiscal_address", "fiscal_address_long", 5, 300),
    ],
)
def test_length_bounds_of_the_required_texts(field: str, short: str, long: str, low: int, high: int) -> None:
    assert error_for(field, "a" * (low - 1)) == MESSAGES[short]
    assert error_for(field, "a" * low) is None
    assert error_for(field, "a" * high) is None
    assert error_for(field, "a" * (high + 1)) == MESSAGES[long]


def test_text_is_trimmed_and_counted_after_trimming() -> None:
    assert value_of("legal_name", "   Alicia Demo \n") == "Alicia Demo"
    assert error_for("legal_name", " " + "a" * 200 + " ") is None  # 200 caracteres reales
    assert value_of("activity", "  Diseño  ") == "Diseño"


def test_the_activity_has_a_ceiling_and_may_be_empty() -> None:
    assert error_for("activity", "a" * 200) is None
    assert error_for("activity", "a" * 201) == MESSAGES["activity"]
    assert value_of("activity", "") is None


@pytest.mark.parametrize("field", ["legal_name", "fiscal_address", "activity"])
@pytest.mark.parametrize(
    "text",
    [
        "Primera\nlínea",
        "Con\ttabulador",
        "Con\rretorno",
        "Ancho\u200bcero",
        "Marca\ufeffBOM",
        "Dirección\u202eoculta",
        "Sepa\u2028rador",
        "Sepa\u2029rador",
        "Nul\x00o",
    ],
)
def test_control_and_format_characters_are_rejected_inside_a_text(field: str, text: str) -> None:
    assert error_for(field, text + " relleno largo") == MESSAGES["control"]


@pytest.mark.parametrize("field", ["legal_name", "fiscal_address", "activity"])
def test_a_non_breaking_space_inside_a_text_is_fine(field: str) -> None:
    assert error_for(field, "Calle\u00a0Mayor 12") is None


@pytest.mark.parametrize("value", [123, 1.5, b"Alicia Demo", ["Alicia"], True, object()])
def test_a_text_field_that_is_not_text_is_a_field_error_not_an_exception(value: object) -> None:
    assert error_for("legal_name", value) == MESSAGES["legal_name"]
    assert error_for("fiscal_address", value) == MESSAGES["fiscal_address"]
    assert error_for("activity", value) == MESSAGES["activity"]
    assert error_for("tax_id", value) == MESSAGES["tax_id"]
    assert error_for("iban", value) == MESSAGES["iban"]
    assert error_for("iae_epigraph", value) == MESSAGES["iae_epigraph"]
    assert error_for("irpf_rate", value) == MESSAGES["irpf_rate"]
    assert error_for("home_pct", value) == MESSAGES["home_pct"]


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("844.1", True),
        ("761", True),
        ("8 44", True),
        ("a" * 20, True),
        ("a" * 21, False),
        ("<script>", False),
        ("٣٤٥", False),
        ("84\n4", False),
        ("A-1", True),
        ("1,5", False),
    ],
)
def test_iae_epigraph(value: str, ok: bool) -> None:
    assert (error_for("iae_epigraph", value) is None) is ok
    assert error_for("iae_epigraph", "") is None


# --- NIF --------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("nif", corpus.ES_ALL)
def test_a_spanish_tax_id_is_stored_as_its_compact_key(nif: str) -> None:
    assert value_of("tax_id", nif) == nif
    assert value_of("tax_id", nif.lower()) == nif
    assert value_of("tax_id", "ES " + nif) == nif  # con el prefijo de país


def test_a_wrong_control_letter_is_not_valid() -> None:
    assert error_for("tax_id", "12345678A") == MESSAGES["tax_id"]
    assert error_for("tax_id", "1234") == MESSAGES["tax_id"]
    assert error_for("tax_id", "ES ES 12345678Z") == MESSAGES["tax_id"]  # doble prefijo (B.2 de SPEC-W-003)
    assert error_for("tax_id", "12345678Z\n") is None  # el salto de línea del final se recorta antes de normalizar


@pytest.mark.parametrize("vat_id", ["DE534861408", "FR89195505110", "EL333906790", "ATU84543291"])
def test_a_valid_eu_vat_number_is_not_a_spanish_tax_id(vat_id: str) -> None:
    assert error_for("tax_id", vat_id) == MESSAGES["tax_id_foreign"]


# --- Fechas --------------------------------------------------------------------------------------------------------------------


def test_start_date_bounds() -> None:
    assert error_for("activity_start_date", date(1950, 1, 1)) is None
    assert error_for("activity_start_date", date(1949, 12, 31)) == MESSAGES["activity_start_date"]
    assert error_for("activity_start_date", TODAY) is None
    assert error_for("activity_start_date", date(2027, 11, 7)) is None  # justo un año
    assert error_for("activity_start_date", date(2027, 11, 8)) == MESSAGES["activity_start_date"]


def test_one_year_after_handles_the_leap_day() -> None:
    assert one_year_after(date(2028, 2, 29)) == date(2029, 2, 28)
    assert one_year_after(date(2027, 2, 28)) == date(2028, 2, 28)
    assert one_year_after(date(2026, 11, 7)) == date(2027, 11, 7)
    leap = validate_profile(RawProfile(activity_start_date=date(2029, 2, 28)), date(2028, 2, 29))
    assert leap.errors == ()
    assert validate_profile(RawProfile(activity_start_date=date(2029, 3, 1)), date(2028, 2, 29)).errors != ()


@pytest.mark.parametrize("value", ["2025-01-15", 20250115, datetime(2025, 1, 15, 10, 0), True, 1.5])
def test_a_start_date_that_is_not_a_date_is_an_error(value: object) -> None:
    assert error_for("activity_start_date", value) == MESSAGES["activity_start_date"]


# --- Régimen ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        (None, True),
        ("", True),
        ("general", True),
        (" general ", True),
        ("General", False),
        ("recargo", False),
        (5, False),
    ],
)
def test_only_the_general_vat_regime(value: object, ok: bool) -> None:
    assert (error_for("vat_regime", value) is None) is ok
    assert value_of("vat_regime", value if ok else None) == "general"


# --- Decimales (D-08, RES-02) ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("7", "7.00"),
        ("7.0", "7.00"),
        ("7.00", "7.00"),
        ("007.00", "7.00"),
        ("15", "15.00"),
        (" 15 ", "15.00"),
        ("15.00", "15.00"),
    ],
)
def test_irpf_rate_accepts_7_and_15_and_stores_two_decimals(raw: str, expected: str) -> None:
    assert error_for("irpf_rate", raw) is None
    assert format_rate(value_of("irpf_rate", raw)) == expected  # type: ignore[arg-type]
    assert value_of("irpf_rate", raw) == Decimal(expected)


@pytest.mark.parametrize(
    "raw",
    [
        "10",
        "0",
        "7.001",
        "1e1",
        "7e0",
        "٧",
        "７",
        "7,00",
        "7.",
        ".7",
        "-7",
        "+7",
        "7 %",
        "15.01",
        "14.99",
        "0007",
        7,
        15,
        7.0,
        Decimal("7"),
        True,
    ],
)
def test_irpf_rate_rejects_everything_else(raw: object) -> None:
    assert error_for("irpf_rate", raw) == MESSAGES["irpf_rate"]


def test_irpf_rate_blank_means_not_chosen() -> None:
    for raw in (None, "", "   "):
        assert value_of("irpf_rate", raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", "0.00"),
        ("30", "30.00"),
        ("30.5", "30.50"),
        ("30.55", "30.55"),
        ("100", "100.00"),
        ("100.00", "100.00"),
        ("99.99", "99.99"),
        ("030", "30.00"),
    ],
)
def test_home_pct_between_0_and_100(raw: str, expected: str) -> None:
    assert value_of("home_pct", raw) == Decimal(expected)
    assert format_rate(value_of("home_pct", raw)) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "raw",
    [
        "100.01",
        "100.1",
        "101",
        "1000",
        "-1",
        "abc",
        "1e2",
        "٣٠",
        "30.555",
        "30,5",
        "30 %",
        30,
        30.5,
        Decimal("30"),
        False,
    ],
)
def test_home_pct_rejects_everything_else(raw: object) -> None:
    assert error_for("home_pct", raw) == MESSAGES["home_pct"]


def test_the_stored_decimals_are_decimals_never_floats() -> None:
    result = check(irpf_rate="7", home_pct="30.1")
    assert result.values is not None
    assert type(result.values.irpf_rate) is Decimal and type(result.values.home_pct) is Decimal
    assert result.values.home_pct == Decimal("30.10")  # un float daría 30.10000000000000142…


# --- IBAN --------------------------------------------------------------------------------------------------------------------


def test_iban_is_stored_compact_and_uppercase() -> None:
    assert value_of("iban", "es91 2100 0418 4502 0005 1332") == corpus_iban.ES_CLASSIC
    assert (
        value_of("iban", "  ES91-2100-0418-4502-0005-1332 \n") == corpus_iban.ES_CLASSIC
    )  # el recorte de los extremos es de aquí


@pytest.mark.parametrize(
    "raw", ["ES9121000418450200051333", corpus_iban.ES_BAD_CCC, "ES00", "no es un iban", "ES91\n2100041845020005133"]
)
def test_a_bad_iban_is_an_error_that_does_not_repeat_the_value(raw: str) -> None:
    message = error_for("iban", raw)
    assert message == MESSAGES["iban"]
    assert raw not in message


def test_messages_never_repeat_what_was_typed() -> None:
    result = check(legal_name="x", tax_id="12345678A", iban="ES00", irpf_rate="10")
    for error in result.errors:
        assert "12345678A" not in error.message and "ES00" not in error.message and "10" not in error.message
