"""Ayudas de las pruebas del PDF: una factura de ejemplo para dibujar, imágenes de logo hechas con Pillow y la extracción de texto con `pypdf`.

Todos los datos son sintéticos y reconocibles (RES-07).
"""

import io
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from PIL import Image
from pypdf import PdfReader

from cuadre.invoicing.types import PdfInvoice

ISSUER_IBAN = "ES3600000000050000000001"


def pdf_invoice(**changes: Any) -> PdfInvoice:
    """La factura de ejemplo: base 1.200,00 € al 21 % con retención del 15 % (total 1.272,00 €), a una empresa española."""
    base = PdfInvoice(
        display_number="2026-001",
        kind="standard",
        issue_date=date(2026, 3, 2),
        issuer_name="Alicia Demo (sintético)",
        issuer_tax_id="12345678Z",
        issuer_address="Calle Ficticia 1, 00000 Ciudad de Pruebas",
        issuer_iban=ISSUER_IBAN,
        client_name="Estudio Norte S.L.",
        client_tax_id="B00000018",
        client_address="Avenida Inventada 4, 28000 Madrid",
        concept="Diseño de identidad visual",
        base_cents=120_000,
        vat_rate=Decimal("21.00"),
        vat_cents=25_200,
        irpf_rate=Decimal("15.00"),
        irpf_cents=18_000,
        total_cents=127_200,
        legal_note=None,
    )
    return replace(base, **changes)


def rectifying(**changes: Any) -> PdfInvoice:
    """Una rectificativa de la anterior a 1.000,00 €: base −200,00 €, IVA −42,00 €, retención −30,00 € y total −212,00 €."""
    defaults: dict[str, Any] = {
        "display_number": "R-2026-001",
        "kind": "rectifying",
        "issue_date": date(2026, 3, 9),
        "base_cents": -20_000,
        "vat_cents": -4_200,
        "irpf_cents": -3_000,
        "total_cents": -21_200,
        "rectifies_number": "2026-001",
        "rectifies_date": date(2026, 3, 2),
        "rectification_reason": "Importe mal calculado",
    }
    return pdf_invoice(**{**defaults, **changes})


def text_of(pdf: bytes) -> str:
    """Todo el texto de todas las páginas, una línea por renglón."""
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def images_of(pdf: bytes) -> int:
    """Cuántas imágenes dibuja la primera página (el logo; el QR es vectorial)."""
    return len(PdfReader(io.BytesIO(pdf)).pages[0].images)


def pages_of(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def metadata_of(pdf: bytes) -> dict[str, str]:
    meta = PdfReader(io.BytesIO(pdf)).metadata
    assert meta is not None
    return {str(k): str(v) for k, v in meta.items()}


def image(fmt: str, width: int = 120, height: int = 60) -> bytes:
    """Un logo sintético de color liso en el formato pedido (PNG, JPEG, WEBP, GIF…)."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (30, 90, 160)).save(buffer, format=fmt)
    return buffer.getvalue()
