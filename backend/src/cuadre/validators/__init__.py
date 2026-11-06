"""Validadores deterministas del gasto (SPEC-W-003, RF-010, US-005, RES-01): Python puro, sin base de datos, sin red y sin reloj propio.

La API los usa para decidir si una lectura se puede registrar; el modelo de lenguaje no interviene. `normalize_tax_id` es la única puerta
a `python-stdnum` y la que blinda su entrada (Anexo B.1 de la spec).
"""

from cuadre.validators.categories import LABELS as CATEGORY_LABELS
from cuadre.validators.categories import ExpenseCategory, suggest_category
from cuadre.validators.checks import validate
from cuadre.validators.duplicates import normalize_invoice_number
from cuadre.validators.tax_id import TaxId, normalize_tax_id
from cuadre.validators.types import (
    Check,
    CheckCode,
    ExistingExpense,
    InvoiceData,
    Preview,
    RegistrableValues,
    TaxLine,
    Validation,
    ValidationContext,
    ValidationWarning,
    WarningCode,
    Withholding,
    from_stored,
)

__all__ = [
    "CATEGORY_LABELS",
    "Check",
    "CheckCode",
    "ExistingExpense",
    "ExpenseCategory",
    "InvoiceData",
    "Preview",
    "RegistrableValues",
    "TaxId",
    "TaxLine",
    "Validation",
    "ValidationContext",
    "ValidationWarning",
    "WarningCode",
    "Withholding",
    "from_stored",
    "normalize_invoice_number",
    "normalize_tax_id",
    "suggest_category",
    "validate",
]
