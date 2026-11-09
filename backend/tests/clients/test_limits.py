"""T6-02 · Las constantes que la base repetirá en CHECK (hito 2) están fijadas aquí: si cambia una, esta prueba obliga a cambiar la migración."""

from cuadre.clients import limits


def test_text_limits_are_the_ones_in_the_spec() -> None:
    assert (limits.NAME_MIN, limits.NAME_MAX) == (2, 200)  # `CHECK (char_length(name) BETWEEN 2 AND 200)`
    assert limits.ADDRESS_MAX == 300  # `CHECK (char_length(address) <= 300)`


def test_forbidden_text_categories() -> None:
    assert {"Cc", "Cf", "Zl", "Zp"} == limits.FORBIDDEN_CATEGORIES


def test_kinds_are_the_enum_of_the_database() -> None:
    assert limits.KINDS == ("business", "individual")  # `client_kind`


def test_country_patterns_are_ascii_only() -> None:
    """`CHECK (country ~ '^[A-Z]{2}$')`; el prefiltro va antes de `upper()` (`"ß"` daría `"SS"`)."""
    assert limits.COUNTRY_CODE.pattern == "[A-Z]{2}"
    assert limits.COUNTRY_RAW.pattern == "[A-Za-z]{2}"
    assert limits.SPAIN == "ES"  # `CHECK ((scope = 'national') = (country = 'ES'))`


def test_the_free_tax_id_is_32_characters_at_most() -> None:
    assert limits.TAX_ID_FREE_MAX == 32  # `CHECK (char_length(tax_id) BETWEEN 1 AND 32)`
    assert limits.TAX_ID_FREE_RAW.pattern == "[0-9A-Za-z .,/-]{1,32}"
    assert limits.TAX_ID_FREE_SEPARATORS == " .-"  # la coma y la barra se conservan en la clave
