"""Reglas de la ficha de cliente (SPEC-W-006 §5.1): validar, normalizar, deducir el ámbito y calcular el VIES simulado. Python puro (T6-01).

`validate_client` mira **todos** los campos y devuelve todos los errores a la vez, en el orden de la pantalla, para pintarlos junto a cada
campo. Un campo vacío es `None`. El NIF y el NIF-IVA los normaliza `cuadre.validators` (única puerta a `python-stdnum`); lo que la librería
**no** hace —comprobar que el prefijo de un NIF-IVA es el del país elegido— lo hace esta regla (Anexo B.1-A).
"""

import unicodedata
from typing import Literal

from cuadre.clients.countries import COUNTRIES
from cuadre.clients.limits import (
    ADDRESS_MAX,
    COUNTRY_RAW,
    FORBIDDEN_CATEGORIES,
    NAME_MAX,
    NAME_MIN,
    TAX_ID_FREE_RAW,
    TAX_ID_FREE_SEPARATORS,
)
from cuadre.clients.scope import scope_of
from cuadre.clients.types import ClientResult, ClientValues, FieldError, Kind, RawClient, Scope
from cuadre.clients.vies import FakeViesChecker, ViesChecker
from cuadre.validators import normalize_tax_id
from cuadre.validators.limits import PREFIX_ALIASES

MESSAGES = {
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

TaxIdMode = Literal["national", "eu_vat", "free"]

_BAD = object()  # el valor no se entendió (tipo inesperado o caracteres de control)
_DEFAULT_CHECKER = FakeViesChecker()


def tax_id_rule(scope: Scope, kind: Kind) -> tuple[TaxIdMode, bool]:
    """Cómo se valida el identificador fiscal y si es obligatorio (D-04): nacional → NIF, NIE o CIF español (obligatorio en una empresa);
    UE y empresa → NIF-IVA del país (obligatorio); el resto → texto libre (obligatorio fuera de la UE y en una empresa)."""
    if scope == "national":
        return "national", kind == "business"
    if scope == "eu" and kind == "business":
        return "eu_vat", True
    return "free", kind == "business"


def vat_prefix(country: str) -> str:
    """El prefijo del NIF-IVA de un país: el propio código, salvo Grecia (`GR` ↔ `EL`)."""
    return PREFIX_ALIASES.get(country, country)


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


def _name(raw: object) -> tuple[str | None, str | None]:
    text = _single_line(raw)
    if text is _BAD:
        return None, MESSAGES["control"] if isinstance(raw, str) else MESSAGES["name"]
    if not isinstance(text, str) or len(text) < NAME_MIN:
        return None, MESSAGES["name"]
    if len(text) > NAME_MAX:
        return None, MESSAGES["name_long"]
    return text, None


def _kind(raw: object) -> tuple[Kind | None, str | None]:
    text = _blank(raw)
    if text == "business":
        return "business", None
    if text == "individual":
        return "individual", None
    return None, MESSAGES["kind"]


def _country(raw: object) -> tuple[str | None, str | None]:
    text = _blank(raw)
    # El prefiltro ASCII va ANTES de `upper()`: `"ß"` daría `"SS"` y `"ı"` daría `"I"`.
    if not isinstance(text, str) or COUNTRY_RAW.fullmatch(text) is None:
        return None, MESSAGES["country"]
    code = text.upper()
    return (code, None) if code in COUNTRIES else (None, MESSAGES["country"])


def _address(raw: object) -> tuple[str | None, str | None]:
    text = _single_line(raw)
    if text is _BAD:
        return None, MESSAGES["control"] if isinstance(raw, str) else MESSAGES["address_long"]
    if not isinstance(text, str):
        return None, None
    return (text, None) if len(text) <= ADDRESS_MAX else (None, MESSAGES["address_long"])


def _free_key(text: str) -> str | None:
    """La clave compacta del texto libre, o `None` si no es un identificador (caracteres no admitidos o nada que comparar)."""
    if TAX_ID_FREE_RAW.fullmatch(text) is None:
        return None
    key = "".join(ch for ch in text.upper() if ch not in TAX_ID_FREE_SEPARATORS)
    return key or None


def _tax_id(raw: object, country: str, scope: Scope, kind: Kind) -> tuple[str | None, str | None]:
    mode, required = tax_id_rule(scope, kind)
    invalid = {
        "national": MESSAGES["tax_id_national"],
        "eu_vat": MESSAGES["tax_id_eu"],
        "free": MESSAGES["tax_id_free"],
    }[mode]
    text = _blank(raw)
    if text is _BAD:
        return None, invalid
    if not isinstance(text, str):
        if not required:
            return None, None
        missing = {
            "national": MESSAGES["tax_id_national_missing"],
            "eu_vat": MESSAGES["tax_id_eu_missing"],
            "free": MESSAGES["tax_id_other_missing"],
        }[mode]
        return None, missing
    if mode == "free":
        key = _free_key(text)
        return (key, None) if key is not None else (None, invalid)
    found = normalize_tax_id(text)
    if found is None:
        return None, invalid
    if mode == "national":
        if found.scope != "national":
            return None, MESSAGES["tax_id_national_foreign"]
        return found.key, None
    # NIF-IVA de la UE: la librería valida el control del país que lleva el propio número; aquí se exige que sea el del cliente.
    if found.scope != "eu" or not found.key.startswith(vat_prefix(country)):
        return None, invalid
    return found.key, None


# --- Operación ------------------------------------------------------------------------------------------------------------------


def validate_client(raw: RawClient, checker: ViesChecker | None = None) -> ClientResult:
    """Valida todos los campos a la vez. O devuelve los valores normalizados, o todos los errores en el orden de la pantalla.

    Si el tipo o el país fallan, **no se juzga** el identificador fiscal: la regla depende de los dos y un error sobre él sería engañoso.
    """
    name, e_name = _name(raw.name)
    kind, e_kind = _kind(raw.kind)
    country, e_country = _country(raw.country)
    address, e_address = _address(raw.address)
    scope: Scope | None = scope_of(country) if country is not None else None
    tax_id: str | None = None
    e_tax: str | None = None
    if kind is not None and country is not None and scope is not None:
        tax_id, e_tax = _tax_id(raw.tax_id, country, scope, kind)
    pairs = (("name", e_name), ("kind", e_kind), ("country", e_country), ("tax_id", e_tax), ("address", e_address))
    errors = tuple(FieldError(field, message) for field, message in pairs if message is not None)
    if errors or name is None or kind is None or country is None or scope is None:
        return ClientResult(None, errors)
    vies = "not_applicable"
    if scope == "eu" and kind == "business" and tax_id is not None:
        vies = (checker or _DEFAULT_CHECKER).check(country, tax_id)
    return ClientResult(ClientValues(name, kind, country, scope, tax_id, address, vies), ())  # type: ignore[arg-type]
