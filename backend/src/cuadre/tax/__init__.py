"""Dominio fiscal de la emisión de facturas y de los modelos 303 y 130 (SPEC-W-007, RF-006; SPEC-W-008 y SPEC-W-009, RF-013): Python puro, sin base de
datos, sin red y sin reloj propio.

Qué IVA, qué retención y qué mención lleva una factura según el ámbito y el tipo del cliente, y cuánto suma; y, con las facturas y los gastos
de un periodo, las casillas del 303 (por trimestre) y del 130 (acumuladas desde enero) con los documentos que las componen. El redondeo es el de
`cuadre.validators.vat` (céntimos enteros, `Decimal` con `ROUND_HALF_UP`); el 303 solo suma y el 130 redondea solo el 20 % de la casilla 04.
"""

from cuadre.tax.amounts import compute_amounts, rectification_amounts
from cuadre.tax.invoice_terms import invoice_terms
from cuadre.tax.limits import DEFAULT_VAT_RATE, NOTE_NON_EU, NOTE_REVERSE_CHARGE, TREATMENTS, VAT_RATES
from cuadre.tax.modelo_130 import build_modelo_130
from cuadre.tax.modelo_303 import QuarterTooLarge, UnsupportedVatRate, build_modelo_303
from cuadre.tax.periods import (
    InvalidPeriod,
    PeriodInFuture,
    deadline_status,
    filing_deadline,
    quarter_bounds,
    quarter_of,
    validate_period,
    year_start,
)
from cuadre.tax.types import Amounts, InvoiceTerms, Standing, TaxTreatment
from cuadre.tax.types_130 import Box130, CostRow, IncomeRow, Item130, Modelo130
from cuadre.tax.types_303 import Box, ExpenseLine, ExpenseRow, InvoiceRow, Item, Modelo303

__all__ = [
    "DEFAULT_VAT_RATE",
    "NOTE_NON_EU",
    "NOTE_REVERSE_CHARGE",
    "TREATMENTS",
    "VAT_RATES",
    "Amounts",
    "Box",
    "Box130",
    "CostRow",
    "ExpenseLine",
    "ExpenseRow",
    "IncomeRow",
    "InvalidPeriod",
    "InvoiceRow",
    "InvoiceTerms",
    "Item",
    "Item130",
    "Modelo130",
    "Modelo303",
    "PeriodInFuture",
    "QuarterTooLarge",
    "Standing",
    "TaxTreatment",
    "UnsupportedVatRate",
    "build_modelo_130",
    "build_modelo_303",
    "compute_amounts",
    "deadline_status",
    "filing_deadline",
    "invoice_terms",
    "quarter_bounds",
    "quarter_of",
    "rectification_amounts",
    "validate_period",
    "year_start",
]
