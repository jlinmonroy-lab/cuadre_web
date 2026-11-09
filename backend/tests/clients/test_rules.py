"""AC-01 a AC-07, AC-14 · La ficha del cliente: campos, ámbito, identificador fiscal por ámbito y tipo, todos los errores a la vez (SPEC-W-006 §5.1)."""

import itertools

import pytest

from cuadre.clients import (
    COUNTRIES,
    EU_COUNTRIES,
    MESSAGES,
    ClientValues,
    RawClient,
    tax_id_rule,
    validate_client,
    vat_prefix,
)
from tests.validators import corpus

ZERO_WIDTH = chr(0x200B)
RLO = chr(0x202E)
LINE_SEP = chr(0x2028)
NBSP = chr(0xA0)
LF, TAB, NUL = chr(10), chr(9), chr(0)

# Cada mensaje de §5.1, tal cual está escrito en la spec.
SPEC_TEXT = {
    "name": "Escribe el nombre o la razón social del cliente.",
    "name_long": "El nombre admite hasta 200 caracteres.",
    "kind": "Elige si es una empresa o profesional, o un particular.",
    "country": "Elige un país de la lista.",
    "address_long": "El domicilio admite hasta 300 caracteres.",
    "control": "No puede llevar saltos de línea ni caracteres de control.",
    "tax_id_national_missing": "Escribe el NIF del cliente.",
    "tax_id_national": "El NIF no es válido: revisa el dígito o la letra de control.",
    "tax_id_national_foreign": "Escribe un NIF, NIE o CIF español.",
    "tax_id_eu_missing": "Escribe el NIF-IVA del cliente.",
    "tax_id_eu": "El NIF-IVA no es válido o no corresponde al país elegido.",
    "tax_id_other_missing": "Escribe el identificador fiscal del cliente.",
    "tax_id_free": "El identificador fiscal solo lleva letras, números y guiones, hasta 32 caracteres.",
}

NIF_B = "B00000018"
VAT_DE = corpus.EU_VAT["DE"]
VAT_FR = corpus.EU_VAT["FR"]
VAT_EL = corpus.EU_VAT["EL"]
DNI = corpus.ES_DNI[0]
NIE = corpus.ES_NIE[0]


def client(**over: object) -> RawClient:
    base: dict[str, object] = {
        "name": "Estudio Norte S.L.",
        "kind": "business",
        "country": "ES",
        "tax_id": NIF_B,
        "address": "Calle Inventada 4, Madrid",
    }
    base.update(over)
    return RawClient(**base)


def values(raw: RawClient) -> ClientValues:
    result = validate_client(raw)
    assert result.errors == (), result.errors
    assert result.values is not None
    return result.values


def errors(raw: RawClient) -> dict[str, str]:
    result = validate_client(raw)
    assert result.values is None
    return {e.field: e.message for e in result.errors}


def test_the_messages_are_the_ones_of_the_spec() -> None:
    assert MESSAGES == SPEC_TEXT


# --- Un cliente de cada ámbito (AC-01 a AC-03) -------------------------------------------------------------------------------------


def test_ac01_a_national_company_is_normalized() -> None:
    found = values(client(name="  Estudio Norte S.L.  ", country=" es ", tax_id=" b-0000 0018 ", address="  Calle 1  "))
    assert found == ClientValues("Estudio Norte S.L.", "business", "ES", "national", NIF_B, "Calle 1", "not_applicable")


def test_ac02_a_german_company_with_a_vat_number() -> None:
    found = values(client(name="Kreativ GmbH", country="de", tax_id=VAT_DE.lower(), address=None))
    assert found == ClientValues("Kreativ GmbH", "business", "DE", "eu", VAT_DE, None, "valid_simulated")


def test_ac03_a_company_and_an_individual_outside_the_eu() -> None:
    company = values(client(name="Taller Zocalo", country="MX", tax_id="mxtest-0001"))
    assert (company.scope, company.tax_id, company.vies_status) == ("non_eu", "MXTEST0001", "not_applicable")
    person = values(client(name="Sam Rivers", kind="individual", country="US", tax_id=None, address=None))
    assert (person.scope, person.tax_id, person.vies_status) == ("non_eu", None, "not_applicable")
    assert errors(client(country="MX", tax_id=None)) == {"tax_id": SPEC_TEXT["tax_id_other_missing"]}


# --- nombre ----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["Ab", "A b", "x" * 200, "  Ñandú S.L.  ", "Café " + NBSP + "Liebre", "Müller & Söhne GmbH", "株式会社"]
)
def test_valid_names(raw: str) -> None:
    assert values(client(name=raw)).name == raw.strip()


@pytest.mark.parametrize("raw", [None, "", "   ", "A", " A ", NBSP + NBSP, 5, 1.5, b"Ab", ["Ab"], {"a": 1}, True])
def test_a_missing_or_short_or_foreign_name_is_the_name_error(raw: object) -> None:
    assert errors(client(name=raw)) == {"name": SPEC_TEXT["name"]}


def test_a_201_character_name_is_too_long() -> None:
    assert errors(client(name="x" * 201)) == {"name": SPEC_TEXT["name_long"]}


@pytest.mark.parametrize("bad", [LF, TAB, NUL, ZERO_WIDTH, RLO, LINE_SEP, chr(0x2029), chr(0x7F), chr(0x85), chr(0xAD)])
def test_a_control_or_format_character_inside_the_name_is_rejected(bad: str) -> None:
    assert errors(client(name=f"Estudio{bad}Norte")) == {"name": SPEC_TEXT["control"]}


def test_a_newline_at_the_ends_is_trimmed() -> None:
    assert values(client(name=LF + "Estudio Norte" + LF)).name == "Estudio Norte"


# --- tipo ------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["business", "individual", " business ", "individual" + LF])
def test_valid_kinds(kind: str) -> None:
    assert values(client(kind=kind, tax_id="AB12", country="MX")).kind == kind.strip()


@pytest.mark.parametrize(
    "kind",
    [
        None,
        "",
        "  ",
        "empresa",
        "particular",
        "Business",
        "BUSINESS",
        "company",
        "business ".replace("s ", "s\t") + "x",
        5,
        True,
        b"business",
        ["business"],
    ],
)
def test_an_unknown_kind_is_the_kind_error(kind: object) -> None:
    assert errors(client(kind=kind)) == {"kind": SPEC_TEXT["kind"]}


# --- país ------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("country", ["ES", "es", " Es ", "DE", "de", "gr", "MX", "us", "GB", "BQ", "SS"])
def test_valid_countries_are_uppercased(country: str) -> None:
    assert values(client(kind="individual", tax_id=None, country=country)).country == country.strip().upper()


@pytest.mark.parametrize(
    "country",
    [
        None,
        "",
        "  ",
        "E",
        "ESP",
        "XI",
        "XK",
        "EU",
        "UK",
        "ZZ",
        "AN",
        "xx",
        "ß",
        "ı",
        "Ñ",
        "ES1",
        "E" + LF + "S",
        "E-",
        "1E",
        5,
        b"ES",
        ["ES"],
        "ｅｓ",
    ],
)
def test_a_country_that_is_not_in_the_catalogue_is_the_country_error(country: object) -> None:
    assert errors(client(kind="individual", tax_id=None, country=country)) == {"country": SPEC_TEXT["country"]}


def test_the_ascii_prefilter_runs_before_the_uppercase() -> None:
    """`"ß".upper()` es `"SS"`, un código válido que la persona no escribió; `"ı".upper()` es `"I"`."""
    assert "ß".upper() == "SS" and "SS" in COUNTRIES
    assert errors(client(kind="individual", tax_id=None, country="ß")) == {"country": SPEC_TEXT["country"]}
    assert errors(client(kind="individual", tax_id=None, country="ıı")) == {"country": SPEC_TEXT["country"]}


@pytest.mark.parametrize("code", sorted(COUNTRIES))
def test_every_country_of_the_catalogue_is_accepted_for_an_individual(code: str) -> None:
    found = values(client(kind="individual", tax_id=None, country=code))
    expected = "national" if code == "ES" else "eu" if code in EU_COUNTRIES else "non_eu"
    assert (found.country, found.scope) == (code, expected)


# --- domicilio -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("raw", [None, "", "   ", LF])
def test_an_empty_address_is_none(raw: object) -> None:
    assert values(client(address=raw)).address is None


def test_address_limits() -> None:
    assert values(client(address="x" * 300)).address == "x" * 300
    assert errors(client(address="x" * 301)) == {"address": SPEC_TEXT["address_long"]}


@pytest.mark.parametrize("bad", [LF, TAB, NUL, ZERO_WIDTH, RLO, LINE_SEP])
def test_a_control_character_inside_the_address_is_rejected(bad: str) -> None:
    assert errors(client(address=f"Calle{bad}1")) == {"address": SPEC_TEXT["control"]}


@pytest.mark.parametrize("raw", [5, 1.5, b"Calle 1", ["Calle 1"], True])
def test_an_address_that_is_not_text_is_a_field_error(raw: object) -> None:
    assert errors(client(address=raw)) == {"address": SPEC_TEXT["address_long"]}


# --- la regla del identificador por ámbito y tipo (D-04) ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scope", "kind", "expected"),
    [
        ("national", "business", ("national", True)),
        ("national", "individual", ("national", False)),
        ("eu", "business", ("eu_vat", True)),
        ("eu", "individual", ("free", False)),
        ("non_eu", "business", ("free", True)),
        ("non_eu", "individual", ("free", False)),
    ],
)
def test_the_six_cells_of_the_tax_id_table(scope: str, kind: str, expected: tuple[str, bool]) -> None:
    assert tax_id_rule(scope, kind) == expected  # type: ignore[arg-type]


def test_greece_is_el() -> None:
    assert vat_prefix("GR") == "EL"
    assert [vat_prefix(code) for code in ("DE", "FR", "ES", "MX")] == ["DE", "FR", "ES", "MX"]


# nacional + empresa: obligatorio y válido


@pytest.mark.parametrize(
    "raw",
    [
        NIF_B,
        "b00000018",
        "ES" + NIF_B,
        "es-" + NIF_B,
        "B 0000 0018",
        " B-00000018 ",
        DNI,
        DNI.lower(),
        "ES" + DNI,
        NIE,
        *corpus.ES_KLM,
        *corpus.ES_CIF,
    ],
)
def test_a_national_company_accepts_every_spanish_form(raw: str) -> None:
    key = values(client(tax_id=raw)).tax_id
    assert key is not None
    assert not key.startswith("ES") and key == key.upper() and " " not in key and "-" not in key


@pytest.mark.parametrize("raw", [None, "", "   ", LF])
def test_a_national_company_needs_a_tax_id(raw: object) -> None:
    assert errors(client(tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_national_missing"]}


@pytest.mark.parametrize(
    "raw",
    [
        "12345678A",
        "B00000019",
        "hola",
        "123",
        "B0000001",
        "ES",
        "12345678",
        "1234567Z" + LF + "1",
        5,
        b"B00000018",
        ["B00000018"],
    ],
)
def test_a_wrong_national_tax_id_is_the_national_error(raw: object) -> None:
    assert errors(client(tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_national"]}


@pytest.mark.parametrize("raw", [VAT_DE, VAT_FR, VAT_EL, corpus.EU_VAT["NL"]])
def test_a_national_client_with_an_eu_vat_number_is_told_to_use_a_spanish_one(raw: str) -> None:
    assert errors(client(tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_national_foreign"]}


# nacional + particular: opcional, pero válido si se escribe


def test_a_national_individual_may_have_no_tax_id() -> None:
    assert values(client(kind="individual", tax_id=None)).tax_id is None
    assert values(client(kind="individual", tax_id="  ")).tax_id is None


def test_a_national_individual_with_a_tax_id_has_it_checked() -> None:
    assert values(client(kind="individual", tax_id=DNI.lower())).tax_id == DNI
    assert errors(client(kind="individual", tax_id="12345678A")) == {"tax_id": SPEC_TEXT["tax_id_national"]}
    assert errors(client(kind="individual", tax_id=VAT_DE)) == {"tax_id": SPEC_TEXT["tax_id_national_foreign"]}


# UE + empresa: NIF-IVA obligatorio, válido y del país


@pytest.mark.parametrize("vat_prefix_key", sorted(corpus.EU_VAT))
def test_every_member_accepts_its_own_vat_number(vat_prefix_key: str) -> None:
    country = "GR" if vat_prefix_key == "EL" else vat_prefix_key
    vat = corpus.EU_VAT[vat_prefix_key]
    for variant in (vat, vat.lower(), vat[:2] + " " + vat[2:], vat[:2] + "-" + vat[2:], f" {vat} "):
        found = values(client(name="Empresa UE", country=country, tax_id=variant))
        assert (found.scope, found.tax_id, found.vies_status) == ("eu", vat, "valid_simulated")


@pytest.mark.parametrize("vat_prefix_key", sorted(corpus.EU_VAT))
def test_every_member_rejects_the_vat_number_of_another_country(vat_prefix_key: str) -> None:
    country = "GR" if vat_prefix_key == "EL" else vat_prefix_key
    others = [vat for key, vat in corpus.EU_VAT.items() if key != vat_prefix_key]
    for vat in others:
        assert errors(client(name="Empresa UE", country=country, tax_id=vat)) == {"tax_id": SPEC_TEXT["tax_id_eu"]}


def test_greece_accepts_the_number_written_with_gr_or_el() -> None:
    digits = VAT_EL[2:]
    assert values(client(country="GR", tax_id="EL" + digits)).tax_id == VAT_EL
    assert values(client(country="GR", tax_id="GR" + digits)).tax_id == VAT_EL
    assert values(client(country="gr", tax_id="gr " + digits)).tax_id == VAT_EL


def test_a_spanish_number_is_not_a_vat_number_for_a_german_company() -> None:
    for raw in (NIF_B, DNI, "ES" + NIF_B):
        assert errors(client(country="DE", tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_eu"]}


@pytest.mark.parametrize("raw", [None, "", "  "])
def test_an_eu_company_needs_a_vat_number(raw: object) -> None:
    assert errors(client(country="DE", tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_eu_missing"]}


@pytest.mark.parametrize(
    "raw",
    [
        "DE1",
        "hola",
        "DE44612077",
        "DE446120775",
        "XI722847175",
        "EU440138732",
        "GB123456789",
        "DE" + LF + "446120774",
        5,
        b"DE446120774",
    ],
)
def test_a_wrong_eu_vat_number_is_the_eu_error(raw: object) -> None:
    assert errors(client(country="DE", tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_eu"]}


def test_the_last_digit_of_a_vat_number_matters() -> None:
    wrong = VAT_DE[:-1] + str((int(VAT_DE[-1]) + 1) % 10)
    assert errors(client(country="DE", tax_id=wrong)) == {"tax_id": SPEC_TEXT["tax_id_eu"]}


# UE + particular, fuera de la UE: texto libre


@pytest.mark.parametrize("country", ["DE", "FR", "GR"])
def test_an_eu_individual_has_an_optional_free_identifier(country: str) -> None:
    assert values(client(kind="individual", country=country, tax_id=None)).tax_id is None
    assert values(client(kind="individual", country=country, tax_id="12 345.abc-9")).tax_id == "12345ABC9"


def test_an_eu_individual_does_not_need_the_prefix_of_the_country() -> None:
    assert (
        values(client(kind="individual", country="DE", tax_id=VAT_FR)).tax_id == VAT_FR
    )  # texto libre: nadie lo valida


@pytest.mark.parametrize("country", ["MX", "US", "GB", "CH", "AR"])
@pytest.mark.parametrize("kind", ["business", "individual"])
def test_outside_the_eu_the_identifier_is_free_text(country: str, kind: str) -> None:
    assert values(client(kind=kind, country=country, tax_id="xaxx-010101.000")).tax_id == "XAXX010101000"


def test_a_company_outside_the_eu_needs_an_identifier_and_an_individual_does_not() -> None:
    assert errors(client(country="MX", tax_id=None)) == {"tax_id": SPEC_TEXT["tax_id_other_missing"]}
    assert values(client(kind="individual", country="MX", tax_id=None)).tax_id is None


def test_the_free_key_keeps_commas_and_slashes_and_drops_spaces_dots_and_hyphens() -> None:
    assert values(client(country="MX", tax_id="ab/12,3 x.y-z")).tax_id == "AB/12,3XYZ"


def test_the_free_identifier_is_32_characters_at_most() -> None:
    assert values(client(country="MX", tax_id="A" * 32)).tax_id == "A" * 32
    assert errors(client(country="MX", tax_id="A" * 33)) == {"tax_id": SPEC_TEXT["tax_id_free"]}
    assert errors(client(country="MX", tax_id="A. " * 11 + "A")) == {
        "tax_id": SPEC_TEXT["tax_id_free"]
    }  # 34 caracteres con separadores (el espacio final se recorta antes de contar)


@pytest.mark.parametrize(
    "raw",
    [
        "...",
        "---",
        " - . ",
        "ab#12",
        "ab@",
        "Ñ1",
        "a" + LF + "b",
        "a" + TAB + "b",
        "a" + ZERO_WIDTH + "b",
        "x_y",
        "(1)",
        5,
        b"A1",
        ["A1"],
    ],
)
def test_a_bad_free_identifier_is_the_free_error(raw: object) -> None:
    assert errors(client(country="MX", tax_id=raw)) == {"tax_id": SPEC_TEXT["tax_id_free"]}


# --- el identificador no se juzga sin tipo o país --------------------------------------------------------------------------------


def test_the_tax_id_is_not_judged_when_the_kind_or_the_country_fail() -> None:
    assert errors(client(kind="x", tax_id="hola")) == {"kind": SPEC_TEXT["kind"]}
    assert errors(client(country="ZZ", tax_id="hola")) == {"country": SPEC_TEXT["country"]}
    assert errors(client(kind=None, country=None, tax_id=None)) == {
        "kind": SPEC_TEXT["kind"],
        "country": SPEC_TEXT["country"],
    }


# --- todos los errores a la vez, en el orden de la pantalla (AC-05) -----------------------------------------------------------------


def test_ac05_every_error_at_once_in_screen_order() -> None:
    raw = RawClient(name="", kind="desconocido", country="zz", tax_id="no importa", address="x" * 301)
    result = validate_client(raw)
    assert result.values is None
    assert [e.field for e in result.errors] == ["name", "kind", "country", "address"]
    assert [e.message for e in result.errors] == [
        SPEC_TEXT["name"],
        SPEC_TEXT["kind"],
        SPEC_TEXT["country"],
        SPEC_TEXT["address_long"],
    ]


def test_the_tax_id_error_sits_between_the_country_and_the_address() -> None:
    result = validate_client(RawClient(name="", kind="business", country="ES", tax_id="12345678A", address="x" * 301))
    assert [e.field for e in result.errors] == ["name", "tax_id", "address"]


def test_an_empty_client_reports_the_three_required_fields() -> None:
    assert [e.field for e in validate_client(RawClient()).errors] == ["name", "kind", "country"]


def test_a_result_has_values_or_errors_never_both() -> None:
    good, bad = validate_client(client()), validate_client(client(name=""))
    assert (good.values is not None, good.errors) == (True, ())
    assert (bad.values is None, len(bad.errors)) == (True, 1)


# --- las respuestas no repiten lo escrito (T6-04) --------------------------------------------------------------------------------


def test_no_message_repeats_what_was_typed() -> None:
    secrets = {
        "name": "Nombre-secreto" + LF,
        "kind": "tipo-secreto",
        "country": "pais-secreto",
        "address": "x" * 300 + "direccion-secreta",
    }
    result = validate_client(RawClient(tax_id="nif-secreto", **secrets))
    text = " ".join(e.message for e in result.errors)
    for secret in ("secreto", "Nombre", "x" * 10):
        assert secret not in text
    for scope_country in ("ES", "DE", "MX"):
        for tax in ("12345678A", "DE999", "ab#cd-secreto"):
            found = validate_client(RawClient("Ok Ok", "business", scope_country, tax))
            assert all(tax not in e.message and "secreto" not in e.message for e in found.errors)


# --- idempotencia y que nada lanza ------------------------------------------------------------------------------------------------


VALID_INPUTS = [
    client(),
    client(name=" Kreativ GmbH ", country="de", tax_id=VAT_DE.lower(), address=None),
    client(country="GR", tax_id="GR" + VAT_EL[2:]),
    client(kind="individual", country="US", tax_id="ab/12-3", address="  1 Main St  "),
    client(country="MX", tax_id="mx test 0001"),
    client(kind="individual", tax_id=None, address=None),
    client(kind="individual", country="DE", tax_id="x y"),
]


@pytest.mark.parametrize("raw", VALID_INPUTS)
def test_validating_a_validated_client_changes_nothing(raw: RawClient) -> None:
    first = values(raw)
    again = values(RawClient(first.name, first.kind, first.country, first.tax_id, first.address))
    assert again == first


HOSTILE = [
    None,
    "",
    NUL,
    "x" * 5000,
    ZERO_WIDTH,
    RLO,
    5,
    1.5,
    b"ES",
    ["ES"],
    {"es": 1},
    True,
    "ß",
    "ES" + LF,
    "B" + NUL + "0",
]


def test_nothing_the_client_sends_can_raise() -> None:
    for name, kind, country in itertools.product(
        HOSTILE, ["business", "individual", *HOSTILE[:6]], ["ES", "DE", "MX", *HOSTILE[:8]]
    ):
        for tax_id, address in itertools.product(HOSTILE, HOSTILE[:6]):
            result = validate_client(RawClient(name, kind, country, tax_id, address))
            assert (result.values is None) != (result.errors == ())
