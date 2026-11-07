"""Constantes de las comprobaciones (SPEC-W-003 §5.1). Un solo sitio: cambiar una es cambiar esta línea y su tabla de pruebas.

Son decisiones de trabajo (D-03) hasta validarlas con DEP-01, igual que el redondeo de ADR-0006. Nada aquí usa `float`.
"""

import re
from datetime import date

# La cuota puede diferir 1 céntimo del tipo (por línea) y el total 1 céntimo de la suma de líneas.
TOLERANCE_CENTS = 1

# Tipos de IVA de un proveedor español (se comparan como números: `21.00` es 21) y tope de la UE, donde cada país tiene los suyos.
VAT_RATES_ES = frozenset({0, 4, 10, 21})
VAT_RATE_MAX_EU = 30

MAX_TAX_LINES = 10  # el mismo tope que la lectura guardada (SPEC-W-002 §5.3)
EARLIEST_DATE = date(2000, 1, 1)
CURRENCY = "EUR"

DOC_TYPES_REGISTRABLE = ("full_invoice", "simplified_invoice", "ticket", "receipt")
DOC_TYPES_WITH_MANDATORY_NUMBER = ("full_invoice",)  # un ticket puede no llevar número

# --- NIF y NIF-IVA (Anexo B.1 de la spec) ---------------------------------------------------------------------------------------

TAX_ID_MAX_LENGTH = 32
# Prefiltro ANTES de llamar a la librería: solo ASCII y solo estos separadores (la librería acepta saltos de línea, NBSP, ligaduras…).
TAX_ID_RAW = re.compile(r"[0-9A-Za-z .-]{1,32}")
TAX_ID_SEPARATORS = " .-"
# Lo que se guarda y se compara: la clave compacta. Coincide con el CHECK de `expenses.supplier_tax_id`.
TAX_ID_KEY = re.compile(r"[A-Z0-9]{5,20}")

SPAIN_PREFIX = "ES"
# Los 26 países de la UE distintos de España, con el prefijo de IVA (Grecia es `EL`). Ni `XI`, ni `EU`, ni `IM`, ni `GB`.
EU_VAT_PREFIXES = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "EL",
        "FI",
        "FR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
    }
)
# La librería acepta `GR` y `EL` y los devuelve como se escribieron: aquí se unifican en el oficial.
PREFIX_ALIASES = {"GR": "EL"}

# --- IBAN (SPEC-W-005 Anexo B.1) --------------------------------------------------------------------------------------------------

IBAN_MAX_LENGTH = 64
# Prefiltro ANTES de llamar a la librería: solo ASCII y estos separadores. `U+00A0` y `U+202F` (copiados de un PDF o de un banco) se pasan a
# espacio antes; todo lo demás que no sea esto (saltos de línea interiores, ancho cero, dígitos de otros alfabetos…) no llega a la librería.
IBAN_RAW = re.compile(r"[0-9A-Za-z .-]{1,64}")
IBAN_SEPARATORS = " .-"
IBAN_SPACES = {"\u00a0": " ", "\u202f": " "}
# Lo que se guarda y se compara: el IBAN compacto (de 15 a 34 caracteres según el país).
IBAN_KEY = re.compile(r"[A-Z0-9]{15,34}")
