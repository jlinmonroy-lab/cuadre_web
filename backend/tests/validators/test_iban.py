"""SPEC-W-005 §5.1, D-09 · IBAN: qué se acepta, qué se rechaza y cómo se normaliza (Anexo B.1)."""

import pytest

from cuadre.validators import normalize_iban
from cuadre.validators.limits import IBAN_KEY, IBAN_RAW
from tests.validators import corpus_iban as corpus

GROUPED = "ES36 0000 0000 0500 0000 0001"


def group(key: str) -> str:
    return " ".join(key[i : i + 4] for i in range(0, len(key), 4))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("es91 2100 0418 4502 0005 1332", corpus.ES_CLASSIC),
        ("ES91-2100-0418-4502-0005-1332", corpus.ES_CLASSIC),
        ("ES91.2100.0418.4502.0005.1332", corpus.ES_CLASSIC),
        ("  ES9121000418450200051332  ", corpus.ES_CLASSIC),
        (GROUPED, corpus.SEED_ALICIA),
        ("ES63 0000 0000 0100 0000 0002", corpus.SEED_BETO),
        (GROUPED.replace(" ", "\u00a0"), corpus.SEED_ALICIA),  # copiado de un PDF
        (GROUPED.replace(" ", "\u202f"), corpus.SEED_ALICIA),
    ],
)
def test_accepted_forms_are_normalized(raw: str, expected: str) -> None:
    assert normalize_iban(raw) == expected


@pytest.mark.parametrize("country", sorted(corpus.IBAN_BY_COUNTRY))
def test_there_is_a_valid_iban_for_each_of_the_89_countries(country: str) -> None:
    key = corpus.IBAN_BY_COUNTRY[country]
    assert normalize_iban(key) == key
    assert normalize_iban(group(key)) == key  # forma agrupada
    assert normalize_iban(group(key).lower()) == key
    assert normalize_iban(normalize_iban(key)) == key  # idempotente


def test_the_corpus_covers_89_countries_and_the_ones_we_name_in_the_spec() -> None:
    assert len(corpus.IBAN_BY_COUNTRY) == 89
    assert {"ES", "DE", "FR", "GB", "PT", "IT", "NL", "BE", "IE", "CH"} <= set(corpus.IBAN_BY_COUNTRY)


@pytest.mark.parametrize(
    "raw",
    [
        "ES9121000418450200051333",  # último dígito cambiado: el módulo 97 lo caza
        "ES91 2100 0418 4502 0005 133",  # un carácter de menos
        "ES91 2100 0418 4502 0005 13320",  # uno de más
        "",
        "   ",
        "ES",
        "ES00",
        "XX0012345678901234",  # país sin IBAN
        "US1234567890123456",
        "ES91\n2100041845020005133",  # salto de línea en medio
        "ES9121000418450200051332\n",  # el prefiltro no recorta: de eso se encarga quien llama
        "\tES9121000418450200051332",
        "ES91\u200b2100041845020005133",  # espacio de ancho cero
        "ES" + "٣" * 22,  # dígitos arábigo-índicos
        "ＥＳ" + "９１" + "2100041845020005" + "1332",  # letras y dígitos de ancho completo
        "ES91_2100_0418_4502_0005_1332",
        "ES9121000418450200051332" * 3,  # 72 caracteres: más que el prefiltro
    ],
)
def test_rejected_inputs(raw: str) -> None:
    assert normalize_iban(raw) is None


@pytest.mark.parametrize("raw", [None, 123, 12.5, b"ES9121000418450200051332", ["ES9121000418450200051332"], object()])
def test_something_that_is_not_text_is_not_valid(raw: object) -> None:
    assert normalize_iban(raw) is None


def test_the_national_check_digits_of_a_spanish_account_matter() -> None:
    """Con el módulo 97 bien pero la CCC mal, un IBAN español no es válido (B.1: 18 de 18). Es lo que desactivaría `check_country=False`."""
    assert normalize_iban(corpus.ES_BAD_CCC) is None
    assert normalize_iban(corpus.ES_CLASSIC) == corpus.ES_CLASSIC


def test_any_last_digit_change_is_caught_in_every_country() -> None:
    survivors = []
    for country, key in corpus.IBAN_BY_COUNTRY.items():
        if not key[-1].isdigit():
            continue
        for digit in "0123456789":
            if digit != key[-1] and normalize_iban(key[:-1] + digit) is not None:
                survivors.append((country, digit))
    assert survivors == []


def test_two_adjacent_characters_swapped_are_caught() -> None:
    survivors = []
    for country, key in corpus.IBAN_BY_COUNTRY.items():
        for i in range(2, len(key) - 1):
            if key[i] != key[i + 1] and normalize_iban(key[:i] + key[i + 1] + key[i] + key[i + 2 :]) is not None:
                survivors.append((country, i))
    assert survivors == []  # con esta semilla (Anexo B.1); el módulo 97 no detecta toda permutación posible


def test_the_patterns_are_the_ones_the_spec_fixes() -> None:
    assert IBAN_RAW.pattern == "[0-9A-Za-z .-]{1,64}"
    assert IBAN_KEY.pattern == "[A-Z0-9]{15,34}"
