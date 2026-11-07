"""Series de facturación (SPEC-W-005 §5.1, D-03): validar el código, la descripción y el número inicial. Python puro."""

import unicodedata
from datetime import date

from cuadre.profile.limits import (
    FORBIDDEN_CATEGORIES,
    SERIES_CODE,
    SERIES_DESCRIPTION_MAX,
    SERIES_FIRST_NUMBER_MAX,
    SERIES_FIRST_NUMBER_MIN,
    SERIES_RAW,
)
from cuadre.profile.types import FieldError, SeriesResult

MESSAGES = {
    "code": "El código de la serie lleva de 1 a 8 letras, números o guiones, sin guion al principio ni al final.",
    "description": "La descripción admite hasta 80 caracteres y no puede llevar saltos de línea.",
    "first_number": "El número inicial es un entero entre 1 y 999999.",
}
DEFAULT_FIRST_NUMBER = 1


def normalize_series_code(raw: object) -> str | None:
    """El código en mayúsculas, o `None`. El prefiltro ASCII va **antes** de `upper()`: `"ß"` pasaría a `"SS"`."""
    if not isinstance(raw, str) or SERIES_RAW.fullmatch(raw) is None:
        return None
    code = raw.upper()
    return code if SERIES_CODE.fullmatch(code) else None


def year_series_code(today: date) -> str:
    """El código de la serie del año (`"2026"`)."""
    return f"{today.year:04d}"


def validate_code(raw: object) -> tuple[str | None, str | None]:
    code = normalize_series_code(raw.strip() if isinstance(raw, str) else raw)
    return (code, None) if code is not None else (None, MESSAGES["code"])


def validate_description(raw: object) -> tuple[str | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, MESSAGES["description"]
    text = raw.strip()
    if len(text) > SERIES_DESCRIPTION_MAX or any(unicodedata.category(ch) in FORBIDDEN_CATEGORIES for ch in text):
        return None, MESSAGES["description"]
    return (text or None), None


def validate_first_number(raw: object) -> tuple[int | None, str | None]:
    # `bool` es un `int` en Python: `True` no es un número inicial.
    if type(raw) is not int or not (SERIES_FIRST_NUMBER_MIN <= raw <= SERIES_FIRST_NUMBER_MAX):
        return None, MESSAGES["first_number"]
    return raw, None


def validate_series(
    code: object, description: object = None, first_number: object = DEFAULT_FIRST_NUMBER
) -> SeriesResult:
    """Valida los tres a la vez (crear una serie). Para editar solo uno, se usan `validate_code`, `validate_description` y
    `validate_first_number` por separado."""
    code_value, e_code = validate_code(code)
    description_value, e_description = validate_description(description)
    number_value, e_number = validate_first_number(DEFAULT_FIRST_NUMBER if first_number is None else first_number)
    errors = tuple(
        FieldError(field, message)
        for field, message in (("code", e_code), ("description", e_description), ("first_number", e_number))
        if message is not None
    )
    if errors:
        return SeriesResult(None, None, None, errors)
    return SeriesResult(code_value, description_value, number_value, ())
