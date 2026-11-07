"""Reglas del perfil (SPEC-W-005 §5.1): validar, decir qué falta para emitir y aconsejar la retención. Python puro (T5-02).

`validate_profile` mira **todos** los campos y devuelve todos los errores a la vez, en el orden de la pantalla, para pintarlos junto a cada
campo. Un campo vacío es `None` (el perfil se puede guardar incompleto: lo que falta para emitir lo dice `completeness`). La fecha de hoy
entra como parámetro. El NIF y el IBAN los normalizan `cuadre.validators`, que es la única puerta a `python-stdnum`.
"""

import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from cuadre.profile.limits import (
    ACTIVITY_MAX,
    DECIMAL_RAW,
    EARLIEST_START,
    FISCAL_ADDRESS_MAX,
    FISCAL_ADDRESS_MIN,
    FORBIDDEN_CATEGORIES,
    HOME_PCT_MAX,
    IAE_RAW,
    IRPF_RATES,
    LEGAL_NAME_MAX,
    LEGAL_NAME_MIN,
    REDUCED_RATE,
    REDUCED_YEARS_AFTER_START,
    REGIME,
    STANDARD_RATE,
)
from cuadre.profile.types import (
    Completeness,
    FieldError,
    Missing,
    ProfileResult,
    ProfileValues,
    RawProfile,
    Retention,
    StoredIdentity,
)
from cuadre.validators import normalize_iban, normalize_tax_id

MESSAGES = {
    "legal_name": "Escribe tu nombre o razón social.",
    "legal_name_long": "El nombre o la razón social admite hasta 200 caracteres.",
    "tax_id": "El NIF no es válido: revisa el dígito o la letra de control.",
    "tax_id_foreign": "Escribe un NIF, NIE o CIF español.",
    "fiscal_address": "Escribe tu domicilio fiscal.",
    "fiscal_address_long": "El domicilio fiscal admite hasta 300 caracteres.",
    "activity": "La actividad admite hasta 200 caracteres.",
    "iae_epigraph": "El epígrafe del IAE solo lleva letras, números y puntos, hasta 20 caracteres.",
    "activity_start_date": "La fecha de alta no puede ser anterior a 1950 ni estar a más de un año.",
    "vat_regime": "En esta versión solo está disponible el régimen general.",
    "irpf_rate": "Elige 7 % o 15 %.",
    "home_pct": "Escribe un porcentaje entre 0 y 100, por ejemplo 30.",
    "iban": "El IBAN no es válido: revisa los dígitos de control.",
    "control": "No puede llevar saltos de línea ni caracteres de control.",
}
WARNING_OUT_OF_PERIOD = (
    "El 7 % solo se aplica el año del alta y los dos siguientes. Con tu fecha de alta ya no te corresponde: "
    "compruébalo con tu gestor o asesor."
)
WARNING_NO_START_DATE = "Indica tu fecha de alta para comprobar que te corresponde el 7 %."
LABELS = {"legal_name": "Nombre o razón social", "tax_id": "NIF", "fiscal_address": "Domicilio fiscal"}

_TWO_PLACES = Decimal("0.01")
_BAD = object()  # el valor no se entendió (tipo inesperado o caracteres de control)


def format_rate(value: Decimal) -> str:
    """`Decimal('7')` es `"7.00"`: siempre dos decimales, que es como viajan y como se guardan."""
    return format(value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP), "f")


# --- Campos ---------------------------------------------------------------------------------------------------------------------


def _blank(raw: object) -> object:
    """`None` si no hay nada, el texto recortado, o `_BAD` si no es texto."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return _BAD
    text = raw.strip()
    return text or None


def _single_line(raw: object) -> object:
    """Como `_blank`, y `_BAD` si lleva caracteres de control, de formato o separadores de línea."""
    text = _blank(raw)
    if isinstance(text, str) and any(unicodedata.category(ch) in FORBIDDEN_CATEGORIES for ch in text):
        return _BAD
    return text


def _sized(raw: object, low: int, high: int, short: str, long: str) -> tuple[str | None, str | None]:
    text = _single_line(raw)
    if text is _BAD:
        return None, MESSAGES["control"] if isinstance(raw, str) else short
    if not isinstance(text, str):
        return None, None
    if len(text) < low:
        return None, short
    if len(text) > high:
        return None, long
    return text, None


def _legal_name(raw: object) -> tuple[str | None, str | None]:
    return _sized(raw, LEGAL_NAME_MIN, LEGAL_NAME_MAX, MESSAGES["legal_name"], MESSAGES["legal_name_long"])


def _fiscal_address(raw: object) -> tuple[str | None, str | None]:
    return _sized(
        raw, FISCAL_ADDRESS_MIN, FISCAL_ADDRESS_MAX, MESSAGES["fiscal_address"], MESSAGES["fiscal_address_long"]
    )


def _tax_id(raw: object) -> tuple[str | None, str | None]:
    text = _blank(raw)
    if text is _BAD:
        return None, MESSAGES["tax_id"]
    if not isinstance(text, str):
        return None, None
    found = normalize_tax_id(text)
    if found is None:
        return None, MESSAGES["tax_id"]
    if found.scope != "national":
        return None, MESSAGES["tax_id_foreign"]
    return found.key, None


def _activity(raw: object) -> tuple[str | None, str | None]:
    text = _single_line(raw)
    if text is _BAD:
        return None, MESSAGES["control"] if isinstance(raw, str) else MESSAGES["activity"]
    if not isinstance(text, str):
        return None, None
    return (text, None) if len(text) <= ACTIVITY_MAX else (None, MESSAGES["activity"])


def _iae(raw: object) -> tuple[str | None, str | None]:
    text = _blank(raw)
    if text is _BAD or (isinstance(text, str) and IAE_RAW.fullmatch(text) is None):
        return None, MESSAGES["iae_epigraph"]
    return (text if isinstance(text, str) else None), None


def one_year_after(today: date) -> date:
    """Hoy más un año; el 29 de febrero pasa a 28."""
    try:
        return today.replace(year=today.year + 1)
    except ValueError:
        return today.replace(year=today.year + 1, day=28)


def _start_date(raw: object, today: date) -> tuple[date | None, str | None]:
    if raw is None:
        return None, None
    # `datetime` es una `date` con hora: no es lo que se pide.
    if type(raw) is not date or raw < EARLIEST_START or raw > one_year_after(today):
        return None, MESSAGES["activity_start_date"]
    return raw, None


def _regime(raw: object) -> tuple[str, str | None]:
    text = _blank(raw)
    if text is None or text == REGIME:
        return REGIME, None
    return REGIME, MESSAGES["vat_regime"]


def _decimal(raw: object) -> object:
    """`None` si no hay nada, el `Decimal`, o `_BAD` si no es una cadena ASCII con la forma `7`, `7.5` o `007.00`."""
    text = _blank(raw)
    if not isinstance(text, str):
        return text
    return Decimal(text) if DECIMAL_RAW.fullmatch(text) else _BAD


def _irpf(raw: object) -> tuple[Decimal | None, str | None]:
    value = _decimal(raw)
    if value is None:
        return None, None
    if not isinstance(value, Decimal) or value not in IRPF_RATES:
        return None, MESSAGES["irpf_rate"]
    return value.quantize(_TWO_PLACES), None


def _home_pct(raw: object) -> tuple[Decimal | None, str | None]:
    value = _decimal(raw)
    if value is None:
        return None, None
    if not isinstance(value, Decimal) or value > HOME_PCT_MAX:
        return None, MESSAGES["home_pct"]
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP), None


def _iban(raw: object) -> tuple[str | None, str | None]:
    text = _blank(raw)
    if text is _BAD:
        return None, MESSAGES["iban"]
    if not isinstance(text, str):
        return None, None
    key = normalize_iban(text)
    return (key, None) if key is not None else (None, MESSAGES["iban"])


# --- Operaciones ----------------------------------------------------------------------------------------------------------------


def validate_profile(raw: RawProfile, today: date) -> ProfileResult:
    """Valida todos los campos a la vez. O devuelve los valores normalizados, o todos los errores en el orden de la pantalla."""
    legal_name, e_legal = _legal_name(raw.legal_name)
    tax_id, e_tax = _tax_id(raw.tax_id)
    address, e_address = _fiscal_address(raw.fiscal_address)
    activity, e_activity = _activity(raw.activity)
    iae, e_iae = _iae(raw.iae_epigraph)
    start, e_start = _start_date(raw.activity_start_date, today)
    regime, e_regime = _regime(raw.vat_regime)
    irpf, e_irpf = _irpf(raw.irpf_rate)
    home, e_home = _home_pct(raw.home_pct)
    iban, e_iban = _iban(raw.iban)
    pairs = (
        ("legal_name", e_legal),
        ("tax_id", e_tax),
        ("fiscal_address", e_address),
        ("activity", e_activity),
        ("iae_epigraph", e_iae),
        ("activity_start_date", e_start),
        ("vat_regime", e_regime),
        ("irpf_rate", e_irpf),
        ("home_pct", e_home),
        ("iban", e_iban),
    )
    errors = tuple(FieldError(field, message) for field, message in pairs if message is not None)
    if errors:
        return ProfileResult(None, errors)
    values = ProfileValues(legal_name, tax_id, address, activity, iae, start, regime, irpf, home, iban)
    return ProfileResult(values, ())


def completeness(stored: StoredIdentity) -> Completeness:
    """Qué falta para poder emitir (D-05, US-007), en este orden. Un valor guardado que ya no se entiende (el NIF de un seed antiguo, un
    extranjero) cuenta como faltante."""
    checks = (
        ("legal_name", _legal_name(stored.legal_name)),
        ("tax_id", _tax_id(stored.tax_id)),
        ("fiscal_address", _fiscal_address(stored.fiscal_address)),
    )
    missing = tuple(
        Missing(field, LABELS[field]) for field, (value, error) in checks if value is None or error is not None
    )
    return Completeness(can_issue=not missing, missing_for_invoicing=missing)


def retention(start: object, rate: object, today: date) -> Retention:
    """Sugerencia y aviso de la retención (D-04), orientativos: el 7 % vale el año del alta y los dos siguientes."""
    if type(start) is not date:
        return Retention(None, None, WARNING_NO_START_DATE if rate == REDUCED_RATE else None)
    until = start.year + REDUCED_YEARS_AFTER_START
    in_period = today.year <= until
    suggested = format_rate(REDUCED_RATE if in_period else STANDARD_RATE)
    warning = WARNING_OUT_OF_PERIOD if rate == REDUCED_RATE and not in_period else None
    return Retention(suggested, until, warning)
