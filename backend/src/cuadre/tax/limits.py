"""Constantes fiscales de la emisión de facturas (SPEC-W-007 §5.1.2). Un solo sitio: cambiar una es cambiar esta línea y su tabla de pruebas.

Los tipos de IVA son los vigentes en 2026 (21, 10 y 4 %: Anexo B.1-B). Las menciones: «Inversión del sujeto pasivo» es literal del art. 6.1.m del
Reglamento de facturación; la del artículo 69 de la Ley del IVA es práctica habitual, no un texto impuesto. Nada aquí usa `float`.
"""

from decimal import Decimal

VAT_RATES = (Decimal("21"), Decimal("10"), Decimal("4"))
DEFAULT_VAT_RATE = Decimal("21")
TWO_PLACES = Decimal("0.01")

NOTE_REVERSE_CHARGE = "Inversión del sujeto pasivo."
NOTE_NON_EU = "Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA)."

TREATMENTS = ("national_vat", "eu_reverse_charge", "eu_consumer_vat", "non_eu_consumer_vat", "non_eu_not_subject")

# --- Modelo 303 (SPEC-W-008 §5.1) ---------------------------------------------------------------------------------------------------

PERIOD_MIN_YEAR = 2000
PERIOD_MAX_YEAR = 9998
# Último día de presentación de cada trimestre natural: (mes, día). El del cuarto cae en enero del año siguiente. Es la fecha del calendario:
# la AEAT la traslada al siguiente día hábil si cae en sábado, domingo o festivo, y esta spec no lo calcula (SPEC-W-008 B.2).
FILING_DEADLINES = {1: (4, 20), 2: (7, 20), 3: (10, 20), 4: (1, 30)}
# Más documentos que esto en un trimestre no caben en una respuesta de una Vercel Function (4,5 MB, ADR-0016).
QUARTER_MAX_DOCUMENTS = 5_000
# Los tratamientos que llevan IVA español; los otros dos (inversión del sujeto pasivo y no sujeta) no llevan ni tipo ni cuota.
VAT_TREATMENTS = ("national_vat", "eu_consumer_vat", "non_eu_consumer_vat")

NOTE_303_DRAFT = "Borrador orientativo calculado con tus registros. No se presenta ante la AEAT desde la aplicación."
NOTE_303_EXCLUSIONS = (
    "No incluye compensaciones de periodos anteriores, prorrata, regímenes especiales, adquisiciones intracomunitarias "
    "ni importaciones. El plazo es el del calendario: la AEAT lo traslada si cae en un día inhábil."
)
NOTE_303_CANARIAS = "No incluye el IGIC ni las operaciones en Canarias, Ceuta y Melilla: si tu actividad o tus clientes están allí, consulta con un asesor."
NOTE_303_349 = "Las operaciones de la casilla 59 también van en el modelo 349."
