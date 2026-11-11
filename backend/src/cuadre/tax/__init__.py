"""Dominio fiscal de la emisión de facturas y del modelo 303 (SPEC-W-007, RF-006; SPEC-W-008, RF-013): Python puro, sin base de datos, sin red
y sin reloj propio.

Qué IVA, qué retención y qué mención lleva una factura según el ámbito y el tipo del cliente, y cuánto suma; y, con las facturas y los gastos
de un trimestre, las casillas del 303 con los documentos que las componen. El redondeo es el de `cuadre.validators.vat` (céntimos enteros,
`Decimal` con `ROUND_HALF_UP`); el 303 solo suma.
"""

from cuadre.tax.amounts import compute_amounts, rectification_amounts
from cuadre.tax.invoice_terms import invoice_terms
from cuadre.tax.limits import DEFAULT_VAT_RATE, NOTE_NON_EU, NOTE_REVERSE_CHARGE, TREATMENTS, VAT_RATES
from cuadre.tax.modelo_303 import QuarterTooLarge, UnsupportedVatRate, build_modelo_303
from cuadre.tax.periods import (
    InvalidPeriod,
    PeriodInFuture,
    deadline_status,
    filing_deadline,
    quarter_bounds,
    quarter_of,
    validate_period,
)
from cuadre.tax.types import Amounts, InvoiceTerms, Standing, TaxTreatment
from cuadre.tax.types_303 import Box, ExpenseLine, ExpenseRow, InvoiceRow, Item, Modelo303

__all__ = [
    "DEFAULT_VAT_RATE",
    "NOTE_NON_EU",
    "NOTE_REVERSE_CHARGE",
    "TREATMENTS",
    "VAT_RATES",
    "Amounts",
    "Box",
    "ExpenseLine",
    "ExpenseRow",
    "InvalidPeriod",
    "InvoiceRow",
    "InvoiceTerms",
    "Item",
    "Modelo303",
    "PeriodInFuture",
    "QuarterTooLarge",
    "Standing",
    "TaxTreatment",
    "UnsupportedVatRate",
    "build_modelo_303",
    "compute_amounts",
    "deadline_status",
    "filing_deadline",
    "invoice_terms",
    "quarter_bounds",
    "quarter_of",
    "rectification_amounts",
    "validate_period",
]
