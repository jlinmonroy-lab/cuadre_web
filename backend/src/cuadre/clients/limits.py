"""Constantes de la ficha de cliente (SPEC-W-006 §5.1). Un solo sitio: cambiar una es cambiar esta línea y su tabla de pruebas.

La base de datos repite varias en CHECK (longitudes, el formato del país): `test_limits_parity.py` las compara (hito 2). Nada aquí usa `float`.
Los países y los Estados miembros de la UE viven en `cuadre.clients.countries`.
"""

import re

# --- Texto -----------------------------------------------------------------------------------------------------------------------

NAME_MIN, NAME_MAX = 2, 200
ADDRESS_MAX = 300
# Categorías Unicode que no se admiten en un campo de texto: control (saltos de línea, tabuladores), formato (ancho cero, marcas de
# dirección que falsean lo que se lee), separador de línea y de párrafo. Las mismas que el perfil.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})

# --- Tipo y país -----------------------------------------------------------------------------------------------------------------

KINDS = ("business", "individual")
# Prefiltro ANTES de pasar a mayúsculas: `"ß".upper()` es `"SS"` y `"ı".upper()` es `"I"`, ASCII que no se escribió.
COUNTRY_RAW = re.compile(r"[A-Za-z]{2}")
COUNTRY_CODE = re.compile(r"[A-Z]{2}")  # `CHECK (country ~ '^[A-Z]{2}$')`
SPAIN = "ES"

# --- Identificador fiscal libre (cliente de la UE particular, de fuera de la UE) ---------------------------------------------------

TAX_ID_FREE_MAX = 32  # `CHECK (char_length(tax_id) BETWEEN 1 AND 32)`
TAX_ID_FREE_RAW = re.compile(r"[0-9A-Za-z .,/-]{1,32}")
# Lo que se guarda y se compara es la clave compacta: mayúsculas y sin estos separadores (la coma y la barra se conservan).
TAX_ID_FREE_SEPARATORS = " .-"
