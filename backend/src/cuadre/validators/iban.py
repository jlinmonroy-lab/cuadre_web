"""IBAN (SPEC-W-005 §5.1, Anexo B.1). Junto a `tax_id.py`, el único módulo del paquete que importa `python-stdnum`.

El spike del hito 0 midió con la versión 2.2 que `iban.validate` comprueba el módulo 97, la estructura del cuerpo de 89 países y, solo en BE, ES,
ME y NO, el módulo nacional (en ES, los dos dígitos de control de la cuenta), que se desactiva con `check_country=False`: aquí **nunca** se
desactiva. No sale a la red, recorta blancos, quita ` -.` y aplica NFKC, así que acepta cosas que no queremos guardar (dígitos de ancho
completo, ligaduras). De ahí el orden: `U+00A0`/`U+202F` a espacio → prefiltro ASCII con `fullmatch` → librería dentro de un
`try` ancho (cualquier excepción es «no válido») → comprobar que lo devuelto es solo `A-Z` y `0-9` de la longitud de un IBAN.
"""

import stdnum.iban as stdnum_iban

from cuadre.validators.limits import IBAN_KEY, IBAN_RAW, IBAN_SPACES

_SPACES = str.maketrans(IBAN_SPACES)


def normalize_iban(raw: object) -> str | None:
    """El IBAN compacto en mayúsculas, o `None` si no es válido por la razón que sea. No lanza nunca."""
    if not isinstance(raw, str):
        return None
    text = raw.translate(_SPACES)
    if IBAN_RAW.fullmatch(text) is None:
        return None
    try:
        key = stdnum_iban.validate(text)  # con la comprobación del país activada: en ES, también la CCC
    except Exception:  # noqa: BLE001 - cualquier fallo de la librería es «no válido» (Anexo B.1 de SPEC-W-003)
        return None
    return key if isinstance(key, str) and IBAN_KEY.fullmatch(key) else None
