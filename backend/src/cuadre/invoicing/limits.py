"""Constantes de la emisión de facturas (SPEC-W-007 §5.1 y B.1). Un solo sitio: cambiar una es cambiar esta línea y su tabla de pruebas.

La base de datos repite varias en CHECK (longitudes, rango del número, importe, el patrón del código rectificativo, la ruta del PDF):
`test_limits_parity.py` las compara (hito 2). Nada aquí usa `float`.
"""

import re

# --- Texto -----------------------------------------------------------------------------------------------------------------------

CONCEPT_MIN, CONCEPT_MAX = 2, 300
REASON_MIN, REASON_MAX = 2, 300
# Mismas categorías que el perfil y los clientes: control (saltos de línea), formato (ancho cero, marcas de dirección) y separadores.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})

# --- Importes y número -----------------------------------------------------------------------------------------------------------

BASE_MIN = 1
BASE_MAX = 9_999_999_999  # 99.999.999,99 €; con IVA y retención cabe de sobra en un `bigint`
NUMBER_MIN, NUMBER_MAX = 1, 999_999  # `CHECK (number BETWEEN 1 AND 999999)`
NUMBER_MIN_DIGITS = 3  # `2026-001`; a partir del 1000, `2026-1000`

# --- Series ----------------------------------------------------------------------------------------------------------------------

SERIES_KINDS = ("standard", "rectifying")
RECTIFYING_CODE = re.compile(
    r"R-[0-9]{4}"
)  # la serie rectificativa del año; las ordinarias no pueden usar estos códigos

# --- Fechas ----------------------------------------------------------------------------------------------------------------------

DATE_RAW = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # ASCII: `\d` casa también otros dígitos Unicode

# --- QR simulado (D-11, B.1-B) ---------------------------------------------------------------------------------------------------

QR_PREFIX = "CUADRE-VERIFACTU-SIMULADO"
QR_SEPARATOR = "|"
QR_CAPTION = "QR VeriFactu simulado, no remitido a la AEAT"
QR_SIZE_MM = 35  # la AEAT pide de 30 a 40
QR_LEVEL = "M"

# --- PDF ------------------------------------------------------------------------------------------------------------------------

LOGO_MAX_PIXELS = 4_000_000  # un PNG de 269 KiB y 88 Mpx cuesta 872 MiB y 2 s (B.1-A)
PDF_HASH_PREFIX = 16  # caracteres de la huella en la ruta
UUID_RAW = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
SHA256_RAW = re.compile(r"[0-9a-f]{64}")
PDF_PATH = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9a-f]{16}\.pdf"
)
