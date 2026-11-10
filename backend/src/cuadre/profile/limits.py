"""Constantes del perfil y de las series (SPEC-W-005 §5.1). Un solo sitio: cambiar una es cambiar esta línea y su tabla de pruebas.

La base de datos repite varias en CHECK (longitudes, el 7 y el 15, el patrón del código de serie, la ruta del logo): `test_limits_parity.py`
las compara (hito 2). Nada aquí usa `float`.
"""

import re
from datetime import date
from decimal import Decimal

# --- Texto -----------------------------------------------------------------------------------------------------------------------

LEGAL_NAME_MIN, LEGAL_NAME_MAX = 2, 200
FISCAL_ADDRESS_MIN, FISCAL_ADDRESS_MAX = 5, 300
ACTIVITY_MAX = 200
IAE_RAW = re.compile(r"[0-9A-Za-z. -]{1,20}")
# Categorías Unicode que no se admiten en un campo de texto: control (saltos de línea, tabuladores), formato (ancho cero, marcas de
# dirección que falsean lo que se lee), separador de línea y de párrafo.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})

# --- Fechas, retención y porcentajes ----------------------------------------------------------------------------------------------

EARLIEST_START = date(1950, 1, 1)
REGIME = "general"  # D-06: el único régimen de IVA de la v1
IRPF_RATES = (Decimal(7), Decimal(15))
REDUCED_RATE = Decimal(7)
STANDARD_RATE = Decimal(15)
REDUCED_YEARS_AFTER_START = 2  # el año del alta y los dos siguientes
# Cadena de un decimal con hasta 2 decimales y SOLO dígitos ASCII (`\d` casa también `٧`; Anexo B.1, bloque C).
DECIMAL_RAW = re.compile(r"[0-9]{1,3}(\.[0-9]{1,2})?")
HOME_PCT_MAX = Decimal(100)

# --- Series ----------------------------------------------------------------------------------------------------------------------

SERIES_CODE_MAX = 8
# Prefiltro ANTES de pasar a mayúsculas: `"ß".upper()` es `"SS"` y `"ı".upper()` es `"I"`, ASCII que no se escribió.
SERIES_RAW = re.compile(r"[0-9A-Za-z-]{1,8}")
SERIES_CODE = re.compile(r"[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?")
# Los códigos `R-AAAA` son de las series rectificativas, que crea la emisión (SPEC-W-007 §5.2): una serie propia no los usa. Se repite aquí
# (este paquete no importa `cuadre.invoicing`) y una prueba compara el patrón con `invoicing.limits.RECTIFYING_CODE`.
SERIES_RESERVED = re.compile(r"R-[0-9]{4}")
SERIES_DESCRIPTION_MAX = 80
SERIES_FIRST_NUMBER_MIN, SERIES_FIRST_NUMBER_MAX = 1, 999_999

# --- Logo ------------------------------------------------------------------------------------------------------------------------

LOGO_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
LOGO_MAX_BYTES = 1_048_576  # 1 MiB, igual que el bucket
LOGO_HEAD_BYTES = 12  # lo que se lee con `Range` para comprobar la firma
PNG_SIGNATURE = bytes.fromhex("89504e470d0a1a0a")
JPEG_SIGNATURE = bytes.fromhex("ffd8ff")
LOGO_BUCKET = "logos"
LOGO_PATH = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f-]{36}\.(png|jpg|webp)")
