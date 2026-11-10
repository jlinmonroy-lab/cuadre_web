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
