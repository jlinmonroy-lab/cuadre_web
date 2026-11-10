"""AC-09, AC-10 · Código, descripción y número inicial de una serie (D-03, §5.1). El patrón del código también lo prueba la base (hito 2)."""

from datetime import date

import pytest

from cuadre.profile import (
    normalize_series_code,
    validate_code,
    validate_description,
    validate_first_number,
    validate_series,
    year_series_code,
)
from cuadre.profile.series import MESSAGES

# Los 19 códigos del spike (B.1, D5): los mismos que se probaron en PostgreSQL.
SPIKE_CODES = {
    "2026": True, "A": True, "AB": True, "FAC": True, "F-1": True, "ABCDEFGH": True, "A-B-C-D": True, "R-2026": True,
    "": False, "-A": False, "A-": False, "ABCDEFGHI": False, "fac": True, "AB CD": False, "A_B": False, "Ñ": False, "A\n": False, "٣": False, "--": False,
}  # fmt: skip


@pytest.mark.parametrize(("raw", "valid"), SPIKE_CODES.items())
def test_the_spike_codes(raw: str, valid: bool) -> None:
    # `fac` en minúsculas se acepta y se pasa a mayúsculas; en la base, el CHECK exige que ya vengan en mayúsculas.
    assert (normalize_series_code(raw) is not None) is valid


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("fac", "FAC"), ("Fac", "FAC"), ("a-b", "A-B"), ("2026", "2026"), ("a1", "A1"), ("abcdefgh", "ABCDEFGH")],
)
def test_lowercase_becomes_uppercase(raw: str, expected: str) -> None:
    assert normalize_series_code(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["ß", "ßa", "ı", "ﬁ", "ＡＢ", "ＦＡＣ", "ǆ", "İ", "a\u200b", "a b", " fac", "fac ", "١٢", "A\u00a0B"],
)
def test_unicode_that_uppercases_into_ascii_is_rejected_before_uppercasing(raw: str) -> None:
    """`"ß".upper()` es `"SS"`, `"ı".upper()` es `"I"` y `"ﬁ".upper()` es `"FI"`: el prefiltro ASCII va antes (B.1)."""
    assert normalize_series_code(raw) is None


@pytest.mark.parametrize("raw", [None, 2026, b"FAC", ["FAC"], 1.5, True])
def test_a_code_that_is_not_text_is_rejected(raw: object) -> None:
    assert normalize_series_code(raw) is None


def test_validate_code_trims_what_the_form_sends() -> None:
    assert validate_code(" fac ") == ("FAC", None)
    assert validate_code("") == (None, MESSAGES["code"])
    assert validate_code(None) == (None, MESSAGES["code"])
    assert validate_code("ß") == (None, MESSAGES["code"])


def test_the_year_series_code() -> None:
    assert year_series_code(date(2026, 11, 7)) == "2026"
    assert year_series_code(date(2026, 12, 31)) == "2026"
    assert year_series_code(date(2027, 1, 1)) == "2027"
    assert year_series_code(date(999, 1, 1)) == "0999"
    assert normalize_series_code(year_series_code(date(2026, 11, 7))) == "2026"  # el código del año es un código válido


@pytest.mark.parametrize(
    ("raw", "ok"),
    [
        (1, True),
        (500, True),
        (999_999, True),
        (0, False),
        (-1, False),
        (1_000_000, False),
        (True, False),
        (False, False),
        ("5", False),
        (5.0, False),
        (None, False),
    ],
)
def test_first_number(raw: object, ok: bool) -> None:
    value, error = validate_first_number(raw)
    assert (error is None) is ok
    assert value == (raw if ok else None)


@pytest.mark.parametrize(
    ("raw", "expected", "ok"),
    [
        (None, None, True),
        ("", None, True),
        ("   ", None, True),
        (" Serie principal ", "Serie principal", True),
        ("a" * 80, "a" * 80, True),
        ("a" * 81, None, False),
        ("a\nb", None, False),
        ("a\u200bb", None, False),
        (5, None, False),
    ],
)
def test_description(raw: object, expected: str | None, ok: bool) -> None:
    value, error = validate_description(raw)
    assert (error is None) is ok
    assert value == expected
    if not ok:
        assert error == MESSAGES["description"]


def test_validate_series_creates_with_defaults() -> None:
    result = validate_series("fac")
    assert (result.code, result.description, result.first_number, result.errors) == ("FAC", None, 1, ())
    assert validate_series("fac", "Principal", 100).first_number == 100
    assert validate_series("fac", None, None).first_number == 1  # sin número inicial, 1


def test_validate_series_reports_every_error_at_once_and_in_order() -> None:
    result = validate_series("-A", "x" * 81, True)
    assert [e.field for e in result.errors] == ["code", "description", "first_number"]
    assert (result.code, result.description, result.first_number) == (None, None, None)


# --- Códigos reservados a las series rectificativas (SPEC-W-007 §5.2) ---------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["R-2026", "r-2026", "R-0000", "R-9999", " R-2027 "])
def test_a_rectifying_code_is_reserved(raw: str) -> None:
    code, message = validate_code(raw)
    assert code is None and message == MESSAGES["code_reserved"]
    assert validate_series(raw).errors[0].message == MESSAGES["code_reserved"]


@pytest.mark.parametrize("raw", ["R-26", "R-20266", "R-202", "XR-2026", "R2026", "R-ABCD", "R-2026A", "2026"])
def test_a_code_that_only_looks_like_a_rectifying_one_is_free(raw: str) -> None:
    code, message = validate_code(raw)
    assert message is None and code == raw.strip().upper()


def test_the_reserved_pattern_is_the_one_of_the_invoicing_domain() -> None:
    """Este paquete no importa `cuadre.invoicing`: se repite el patrón y esta prueba obliga a que sea el mismo."""
    from cuadre.invoicing.limits import RECTIFYING_CODE
    from cuadre.profile.limits import SERIES_RESERVED

    assert SERIES_RESERVED.pattern == RECTIFYING_CODE.pattern
