"""NIF y NIF-IVA del proveedor (SPEC-W-003 §5.1, Anexo B.1). Único módulo del paquete que importa `python-stdnum`.

La librería hace el cálculo de los dígitos de control (T3-04), pero **no se le puede dar la entrada tal cual**. El spike del hito 0 midió que:

* acepta `XI` (Irlanda del Norte) y `EU` (OSS), que no son un Estado miembro, y conserva `GR` y `EL` como se escriban;
* no quita los separadores igual en todos los países;
* valida un DNI, un NIE o un K, L, M con un salto de línea en medio y devuelve un resultado con el salto dentro, y con el CIF lanza
  `ValueError`, que no es `ValidationError`.

De ahí el orden: prefiltro ASCII con `fullmatch` → quitar separadores → lista blanca de países → librería dentro de un `try` ancho (cualquier
excepción es «no válido») → comprobar que lo devuelto es solo `A-Z` y `0-9`. Sin red: `validate` no la usa (la consulta a VIES es `check_vies`,
que aquí no se llama, y su extra `zeep` no se instala).
"""

from dataclasses import dataclass
from typing import Literal

from stdnum.es import nif as es_nif
from stdnum.eu import vat as eu_vat

from cuadre.validators.limits import (
    EU_VAT_PREFIXES,
    PREFIX_ALIASES,
    SPAIN_PREFIX,
    TAX_ID_KEY,
    TAX_ID_RAW,
    TAX_ID_SEPARATORS,
)


@dataclass(frozen=True, slots=True)
class TaxId:
    """Un identificador fiscal válido. `key` es la clave compacta que se guarda y se compara: la española **sin** `ES`, la de la UE **con** su
    prefijo (Grecia siempre como `EL`)."""

    scope: Literal["national", "eu"]
    key: str


def normalize_tax_id(raw: object) -> TaxId | None:
    """Devuelve el identificador normalizado, o `None` si no es válido por la razón que sea. No lanza nunca."""
    if not isinstance(raw, str) or TAX_ID_RAW.fullmatch(raw) is None:
        return None
    compact = "".join(ch for ch in raw if ch not in TAX_ID_SEPARATORS).upper()
    if not compact:
        return None
    try:
        if compact[:2].isalpha():
            prefix = compact[:2]
            if prefix == SPAIN_PREFIX:
                return _spanish(compact[2:])
            prefix = PREFIX_ALIASES.get(prefix, prefix)
            if prefix not in EU_VAT_PREFIXES:
                return None
            key = eu_vat.validate(prefix + compact[2:])
            if not isinstance(key, str) or not key.startswith(prefix):
                return None
            return _checked("eu", key)
        return _spanish(compact)
    except Exception:  # noqa: BLE001 - la librería lanza algo que no es ValidationError con ciertas entradas (Anexo B.1)
        return None


def _spanish(body: str) -> TaxId | None:
    # La librería quita un `ES` inicial por su cuenta: sin esta guarda, `ES ES 12345678Z` (doble prefijo) pasaría por válido.
    if body.startswith(SPAIN_PREFIX):
        return None
    key = es_nif.validate(body)
    return _checked("national", key) if isinstance(key, str) else None


def _checked(scope: Literal["national", "eu"], key: str) -> TaxId | None:
    """Defensa en profundidad: lo que se guarda es solo `A-Z` y `0-9`, y cabe en el CHECK de la base de datos."""
    return TaxId(scope, key) if TAX_ID_KEY.fullmatch(key) is not None else None
