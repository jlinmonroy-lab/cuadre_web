"""AC-16, B.1-A · El logo del PDF: se dibuja si es PNG, JPEG o WebP y mide 4 Mpx o menos; si no, la factura sale sin él (SPEC-W-007 §5.1.6).

Un PNG de 269 KiB puede tener 88 Mpx y costar 872 MiB al dibujarlo: las dimensiones se leen SIN decodificar los píxeles y un logo que no cabe ni se abre.
"""

from typing import Any

import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader

from cuadre.invoicing import pdf as pdf_module
from cuadre.invoicing.pdf import logo_image, render_invoice_pdf
from tests.invoicing.pdf_support import image, pdf_invoice


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_the_three_formats_are_drawn(fmt: str) -> None:
    assert isinstance(logo_image(image(fmt)), ImageReader)
    assert render_invoice_pdf(pdf_invoice(), image(fmt)) != render_invoice_pdf(pdf_invoice())


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_formats_are_not_drawn(fmt: str) -> None:
    assert logo_image(image(fmt)) is None
    assert render_invoice_pdf(pdf_invoice(), image(fmt)) == render_invoice_pdf(pdf_invoice())


def test_the_limit_is_four_megapixels_exactly() -> None:
    assert logo_image(image("PNG", 2000, 2000)) is not None  # 4.000.000 px
    assert logo_image(image("PNG", 2000, 2001)) is None
    assert logo_image(image("PNG", 4001, 1000)) is None
    assert logo_image(image("PNG", 4000, 1000)) is not None


def test_the_dimensions_are_read_without_decoding_a_single_pixel(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Image.open(...).size` lee la cabecera; decodificar (`load`) un PNG de 88 Mpx costaría 872 MiB. Ni el que cabe ni el que no se decodifican al medir."""

    def boom(self: Any, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("se decodificaron los píxeles al medir el logo")

    huge, small = (
        image("PNG", 3000, 2000),
        image("PNG"),
    )  # se fabrican ANTES de prohibir `load` (guardarlas también decodifica)
    monkeypatch.setattr(Image.Image, "load", boom)
    assert logo_image(huge) is None
    assert logo_image(small) is not None


def test_an_oversized_logo_is_never_opened_for_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No se construye el lector de imágenes (que es quien decodifica) para un logo que no cabe."""
    calls: list[Any] = []

    def boom(*args: Any, **kwargs: Any) -> None:
        calls.append(args)
        raise AssertionError("no debe leerse un logo de más de 4 Mpx")

    monkeypatch.setattr(pdf_module, "ImageReader", boom)
    assert logo_image(image("PNG", 3000, 2000)) is None
    assert calls == []
    assert render_invoice_pdf(pdf_invoice(), image("PNG", 3000, 2000)) == render_invoice_pdf(pdf_invoice())


@pytest.mark.parametrize(
    "data", [None, b"", b"no es una imagen", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, image("PNG")[:40]]
)
def test_a_missing_or_unreadable_logo_means_no_logo_and_no_error(data: bytes | None) -> None:
    assert logo_image(data) is None
    assert render_invoice_pdf(pdf_invoice(), data) == render_invoice_pdf(pdf_invoice())


def test_a_logo_that_opens_but_cannot_be_decoded_does_not_break_the_invoice() -> None:
    """La cabecera de un PNG válido seguida de basura: `Image.open` la acepta y la decodificación falla al dibujar."""
    broken = image("PNG", 300, 300)[:-60]
    assert render_invoice_pdf(pdf_invoice(), broken)  # no lanza


def test_the_logo_is_deterministic() -> None:
    logo = image("PNG")
    assert render_invoice_pdf(pdf_invoice(), logo) == render_invoice_pdf(pdf_invoice(), logo)
    assert render_invoice_pdf(pdf_invoice(), image("PNG", 60, 30)) != render_invoice_pdf(pdf_invoice(), logo)
