"""Dominio fiscal de la emisión de facturas (SPEC-W-007, RF-006): Python puro, sin base de datos, sin red y sin reloj propio.

Qué IVA, qué retención y qué mención lleva una factura según el ámbito y el tipo del cliente, y cuánto suma. El redondeo es el de
`cuadre.validators.vat` (céntimos enteros, `Decimal` con `ROUND_HALF_UP`).
"""

from cuadre.tax.amounts import compute_amounts, rectification_amounts
from cuadre.tax.invoice_terms import invoice_terms
from cuadre.tax.limits import DEFAULT_VAT_RATE, NOTE_NON_EU, NOTE_REVERSE_CHARGE, TREATMENTS, VAT_RATES
from cuadre.tax.types import Amounts, InvoiceTerms, Standing, TaxTreatment

__all__ = [
    "DEFAULT_VAT_RATE",
    "NOTE_NON_EU",
    "NOTE_REVERSE_CHARGE",
    "TREATMENTS",
    "VAT_RATES",
    "Amounts",
    "InvoiceTerms",
    "Standing",
    "TaxTreatment",
    "compute_amounts",
    "invoice_terms",
    "rectification_amounts",
]
