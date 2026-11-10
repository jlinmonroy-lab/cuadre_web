"""Dominio de la emisión de facturas (SPEC-W-007, RF-006 y RF-007): Python puro, sin base de datos, sin red y sin reloj propio.

La API lo usa para validar una factura y una rectificativa, numerarlas para mostrarlas, componer el contenido del QR simulado y la ruta del PDF.
Las condiciones y los importes fiscales viven en `cuadre.tax`.
"""

from cuadre.invoicing.logo import logo_fits
from cuadre.invoicing.numbering import display_number, is_out_of_order, is_reserved_series_code, rectifying_series_code
from cuadre.invoicing.qr import format_qr_amount, format_qr_date, qr_payload
from cuadre.invoicing.rectification import standing_of
from cuadre.invoicing.rules import MESSAGES, parse_uuid, validate_invoice, validate_rectification
from cuadre.invoicing.storage_path import invoice_pdf_path, pdf_path_owner
from cuadre.invoicing.texts import long_date, numeric_date, rectification_reference
from cuadre.invoicing.types import (
    ClientCopy,
    FieldError,
    InvoiceResult,
    InvoiceValues,
    OriginalInvoice,
    Problem,
    RawInvoice,
    RawRectification,
    RectificationResult,
    RectificationValues,
    SeriesInfo,
)

__all__ = [
    "MESSAGES",
    "ClientCopy",
    "FieldError",
    "InvoiceResult",
    "InvoiceValues",
    "OriginalInvoice",
    "Problem",
    "RawInvoice",
    "RawRectification",
    "RectificationResult",
    "RectificationValues",
    "SeriesInfo",
    "display_number",
    "format_qr_amount",
    "format_qr_date",
    "invoice_pdf_path",
    "is_out_of_order",
    "is_reserved_series_code",
    "logo_fits",
    "long_date",
    "numeric_date",
    "parse_uuid",
    "pdf_path_owner",
    "qr_payload",
    "rectification_reference",
    "rectifying_series_code",
    "standing_of",
    "validate_invoice",
    "validate_rectification",
]
