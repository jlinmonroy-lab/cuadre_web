"""AC-03 y AC-04 · NIF español y NIF-IVA de la UE (SPEC-W-003 §5.1, Anexo B.1)."""

import pytest
from stdnum.es import nif as es_nif
from stdnum.eu import vat as eu_vat
from stdnum.exceptions import ValidationError

from cuadre.validators import TaxId, normalize_tax_id
from cuadre.validators.limits import EU_VAT_PREFIXES, TAX_ID_KEY
from tests.validators import corpus

DIGITS_AND_LETTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def spanish_variants(value: str) -> list[str]:
    return [
        value,
        value.lower(),
        "ES" + value,
        "es" + value.lower(),
        "ES " + value,
        "ES-" + value,
        "ES." + value,
        value[:1] + " " + value[1:-1] + " " + value[-1],
        value[:-1] + "-" + value[-1],
        " " + value + " ",
        value[:2]
        + "."
        + value[2:5]
        + "."
        + value[5:-1]
        + "-"
        + value[-1],  # puntos de millar: la librería los rechaza, aquí se quitan
    ]


# --- España -----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", corpus.ES_ALL)
def test_a_valid_spanish_number_normalizes_to_its_compact_key(value: str) -> None:
    assert normalize_tax_id(value) == TaxId("national", value)


@pytest.mark.parametrize("value", corpus.ES_ALL)
def test_spanish_numbers_accept_prefix_case_and_separators_and_give_the_same_key(value: str) -> None:
    for raw in spanish_variants(value):
        assert normalize_tax_id(raw) == TaxId("national", value), raw


@pytest.mark.parametrize("value", corpus.ES_ALL)
def test_a_wrong_control_character_is_rejected(value: str) -> None:
    rejected = [c for c in DIGITS_AND_LETTERS if c != value[-1] and not es_nif.is_valid(value[:-1] + c)]
    assert rejected, "el corpus debe poder producir un control que la librería rechace"
    for c in rejected[:5]:
        assert normalize_tax_id(value[:-1] + c) is None


def test_k_l_and_m_are_accepted_like_the_library_does() -> None:
    assert all(normalize_tax_id(v) == TaxId("national", v) for v in corpus.ES_KLM)


def test_the_cif_accepts_either_control_form_in_every_type_a_known_limit_of_the_library() -> None:
    """Anexo B.1: la regla habitual pide letra en P, Q, R, S, N y W y dígito en A, B, E y H, y la librería acepta las dos formas siempre."""
    digit_form = normalize_tax_id("A30789028")  # A, control numérico
    letter_form = normalize_tax_id("A3078902H")  # A, control con letra: la regla habitual lo rechazaría
    assert digit_form is not None and letter_form is not None


@pytest.mark.parametrize(
    "value", ["12345678", "12345678Z0", "1234567Z", "123456789Z", "ES", "ES ", "", " ", "-", "...", "- . -"]
)
def test_wrong_lengths_and_empty_values_are_rejected(value: str) -> None:
    assert normalize_tax_id(value) is None


@pytest.mark.parametrize("value", [None, 12345678, b"12345678Z", ["12345678Z"], 1.5, True])
def test_values_that_are_not_text_are_rejected_without_raising(value: object) -> None:
    assert normalize_tax_id(value) is None


def test_more_than_32_characters_are_rejected_even_if_the_number_is_valid() -> None:
    assert normalize_tax_id("12345678Z" + " " * 23) is not None  # 32 caracteres: el máximo
    assert normalize_tax_id("12345678Z" + " " * 24) is None  # 33


@pytest.mark.parametrize("raw", ["ESES12345678Z", "ES ES 12345678Z", "es-es-12345678z", "ES.ES.12345678Z"])
def test_a_doubled_spanish_prefix_is_rejected(raw: str) -> None:
    """La librería quita un `ES` inicial por su cuenta: sin la guarda de `_spanish`, el doble prefijo pasaría por válido."""
    assert normalize_tax_id(raw) is None


# --- UE ----------------------------------------------------------------------------------------------------------------------------


def test_the_corpus_covers_the_26_member_states_besides_spain() -> None:
    assert set(corpus.EU_VAT) == set(EU_VAT_PREFIXES)
    assert len(corpus.EU_VAT) == 26


@pytest.mark.parametrize("country", sorted(corpus.EU_VAT))
def test_a_valid_eu_vat_number_keeps_its_prefix(country: str) -> None:
    value = corpus.EU_VAT[country]
    assert normalize_tax_id(value) == TaxId("eu", value)


@pytest.mark.parametrize("country", sorted(corpus.EU_VAT))
def test_eu_numbers_accept_a_lowercase_prefix_and_every_separator(country: str) -> None:
    """La librería no quita los guiones en CZ y EE ni los puntos en 15 países: el normalizador lo hace antes de llamar."""
    value = corpus.EU_VAT[country]
    prefix, body = value[:2], value[2:]
    variants = [value.lower(), prefix.lower() + body]
    for separator in (" ", "-", "."):
        variants += [prefix + separator + body[:3] + separator + body[3:], prefix + separator + body]
    for raw in variants:
        assert normalize_tax_id(raw) == TaxId("eu", value), raw


@pytest.mark.parametrize("country", sorted(corpus.EU_VAT))
def test_an_eu_number_with_a_wrong_digit_is_rejected(country: str) -> None:
    value = corpus.EU_VAT[country]
    prefix, body = value[:2], value[2:]
    rejected = [
        prefix + body[:i] + d + body[i + 1 :]
        for i, c in enumerate(body)
        if c.isdigit()
        for d in "0123456789"
        if d != c and not eu_vat.is_valid(prefix + body[:i] + d + body[i + 1 :])
    ]
    assert rejected, "debe existir una mutación que la librería rechace"
    assert all(normalize_tax_id(raw) is None for raw in rejected[:20])


def test_greece_is_always_stored_as_el_even_if_written_gr() -> None:
    body = corpus.EU_VAT["EL"][2:]
    keys = {normalize_tax_id(prefix + body) for prefix in ("EL", "GR", "el", "gr", "El")}
    assert keys == {TaxId("eu", "EL" + body)}
    assert normalize_tax_id("GR " + body) == normalize_tax_id("EL" + body)


def test_a_greek_number_of_eight_digits_is_completed_with_a_leading_zero_by_the_library() -> None:
    assert normalize_tax_id("EL33390690") == TaxId("eu", "EL033390690")
    assert normalize_tax_id("GR33390690") == TaxId("eu", "EL033390690")


@pytest.mark.parametrize(
    "raw",
    [
        corpus.XI,  # la librería lo acepta (Irlanda del Norte)
        corpus.EU_OSS,  # esquema OSS: tampoco es un Estado miembro
        "GB" + corpus.XI[2:],
        "IM" + corpus.XI[2:],
        "CHE840621087",
        "NO591182667MVA",
        "US295573523",
        "XX" + corpus.EU_VAT["DE"][2:],
        "DEU" + corpus.EU_VAT["DE"][2:],
        "D" + corpus.EU_VAT["DE"][2:],
        corpus.EU_VAT["DE"][2:],  # sin prefijo de país
        "DE",
        "DEDE" + corpus.EU_VAT["DE"][2:],
        "ELEL" + corpus.EU_VAT["EL"][2:],
    ],
)
def test_prefixes_outside_the_whitelist_and_malformed_prefixes_are_rejected(raw: str) -> None:
    assert normalize_tax_id(raw) is None


def test_the_library_accepts_xi_and_eu_so_the_whitelist_is_what_rejects_them() -> None:
    assert eu_vat.is_valid(corpus.XI) and eu_vat.is_valid(corpus.EU_OSS)
    assert normalize_tax_id(corpus.XI) is None and normalize_tax_id(corpus.EU_OSS) is None


def test_romania_validates_very_short_numbers_a_known_weakness_of_the_library() -> None:
    assert normalize_tax_id("RO9573") == TaxId("eu", "RO9573")


# --- Propiedades de la clave -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [*corpus.ES_ALL, *corpus.EU_VAT.values()])
def test_every_key_fits_the_database_check_and_normalizing_it_again_gives_the_same_result(value: str) -> None:
    result = normalize_tax_id(value)
    assert result is not None
    assert TAX_ID_KEY.fullmatch(result.key) is not None
    assert 5 <= len(result.key) <= 20
    assert normalize_tax_id(result.key) == result


def test_the_shortest_and_longest_keys_are_the_ones_measured_by_the_spike() -> None:
    lengths = [len(normalize_tax_id(v).key) for v in [*corpus.ES_ALL, *corpus.EU_VAT.values()]]  # type: ignore[union-attr]
    assert (min(lengths), max(lengths)) == (6, 14)


# --- Entradas hostiles (Anexo B.1: la librería las acepta o lanza ValueError) --------------------------------------------------------


HOSTILE = corpus.hostile_inputs()


def test_the_hostile_corpus_has_the_size_measured_by_the_spike() -> None:
    assert {family: len(items) for family, items in HOSTILE.items()} == {
        "insertadas": 845,
        "cifras_parecidas": 147,
        "sustituidas": 767,
        "fabricadas_con_salto_de_linea": 610,
    }
    assert sum(len(items) for items in HOSTILE.values()) == 2369


@pytest.mark.parametrize("family", sorted(HOSTILE))
def test_no_hostile_input_passes_or_raises(family: str) -> None:
    passed = []
    for raw in HOSTILE[family]:
        if normalize_tax_id(raw) is not None:  # nunca debe lanzar: si lo hiciera, el test fallaría aquí
            passed.append(raw)
    assert passed == []


def test_the_library_alone_accepts_the_crafted_inputs_so_the_prefilter_is_what_blocks_them() -> None:
    """Es lo que hace que el test anterior signifique algo: si la librería los rechazara, quitar el prefiltro no se notaría."""
    accepted, raising, rejected = [], [], []
    for raw in HOSTILE["fabricadas_con_salto_de_linea"]:
        try:
            result = es_nif.validate(raw)
        except ValidationError:
            rejected.append(raw)
        except ValueError:  # ni siquiera `is_valid` lo captura: solo atrapa `ValidationError`
            raising.append(raw)
        else:
            accepted.append((raw, result))
    assert len(accepted) == 440  # DNI 200, NIE 120 y K/L/M 120: la librería los valida...
    assert all(chr(10) in result for _, result in accepted)  # ...y devuelve el salto de línea dentro
    assert len(raising) == 170  # los CIF: `ValueError`, que no es `ValidationError`
    assert rejected == []


def test_whitespace_the_library_would_strip_is_still_rejected_by_the_prefilter() -> None:
    for ch in (chr(9), chr(10), chr(13), chr(0xA0), chr(0x2028)):
        assert normalize_tax_id(ch + "12345678Z") is None
        assert normalize_tax_id("12345678Z" + ch) is None
        assert es_nif.is_valid(ch + "12345678Z"), "la librería sí los recorta"


def test_ligatures_and_wide_characters_are_rejected_before_the_library_normalizes_them() -> None:
    fi = corpus.EU_VAT["FI"]
    assert eu_vat.is_valid(corpus.LIGATURE_FI + fi[2:]), "la librería convierte la ligadura en FI"
    assert normalize_tax_id(corpus.LIGATURE_FI + fi[2:]) is None
    assert normalize_tax_id("１２３４５６７８Z") is None  # cifras de ancho completo
    assert normalize_tax_id("12345678Ｚ") is None  # letra de ancho completo
