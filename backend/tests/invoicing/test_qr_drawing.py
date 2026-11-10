"""AC-17, D-11, B.1-B · El QR simulado del PDF: nivel M, 35 mm, arriba y centrado, con el texto de §5.1.6 y su leyenda (SPEC-W-007 hito 4).

El QR se comprueba por su construcción (nivel, tamaño, posición, texto y matriz de módulos). El spike del hito 0 lo decodificó con `zxing-cpp` y
devolvió el mismo texto; ese decodificador no es una dependencia del proyecto (solo de comprobaciones a mano, con código nativo).
"""

import math
from datetime import date
from typing import Any

import pytest
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from cuadre.invoicing import pdf as pdf_module
from cuadre.invoicing.pdf import qr_widget, render_invoice_pdf
from cuadre.invoicing.qr import qr_payload
from tests.invoicing.pdf_support import pdf_invoice, rectifying

PAYLOAD = qr_payload("12345678Z", "2026-001", date(2026, 3, 2), 127_200)


def modules(widget: Any) -> list[list[bool]]:
    widget.getBounds()  # el widget codifica el texto al medirse o dibujarse, no al crearse
    count = widget.qr.getModuleCount()
    return [[bool(widget.qr.isDark(r, c)) for c in range(count)] for r in range(count)]


def test_the_payload_is_the_simulated_text_of_the_spec() -> None:
    assert PAYLOAD == "CUADRE-VERIFACTU-SIMULADO|12345678Z|2026-001|02-03-2026|1272.00"
    assert qr_widget(PAYLOAD).value == PAYLOAD


def test_the_widget_is_level_m_and_35_mm() -> None:
    widget = qr_widget(PAYLOAD)
    assert widget.barLevel == "M"
    assert math.isclose(widget.barWidth, 35 * mm) and math.isclose(widget.barHeight, 35 * mm)


def test_the_matrix_is_deterministic_and_depends_on_the_text() -> None:
    first, again = modules(qr_widget(PAYLOAD)), modules(qr_widget(PAYLOAD))
    other = modules(qr_widget(qr_payload("12345678Z", "2026-002", date(2026, 3, 2), 127_200)))
    assert first == again and first != other
    assert len(first) == 37  # versión 5 (37x37 módulos) para este texto, como midió el spike
    assert sum(map(sum, first)) == sum(map(sum, again))


def test_a_rectification_qr_carries_the_signed_amount() -> None:
    payload = qr_payload("12345678Z", "R-2026-001", date(2026, 3, 9), -21_200)
    assert payload.endswith("|09-03-2026|-212.00")
    assert modules(qr_widget(payload)) != modules(qr_widget(PAYLOAD))


def test_the_worst_case_payload_fits_the_same_qr_version() -> None:
    """NIF español de 9, serie de 8 y 6 dígitos, importe de 15 caracteres: 76 caracteres caben en la versión 5-M (84 en modo de bytes; B.2)."""
    payload = qr_payload("X1234567L", "ABCDEFGH-999999", date(2026, 12, 31), -9_999_999_999)
    assert len(payload) <= 84
    assert len(modules(qr_widget(payload))) == 37


@pytest.mark.parametrize("invoice", [pdf_invoice(), rectifying()])
def test_the_pdf_draws_the_qr_at_the_top_centered_with_35_mm(monkeypatch: pytest.MonkeyPatch, invoice: Any) -> None:
    seen: list[tuple[float, float, float, float]] = []
    real = renderPDF.draw

    def spy(drawing: Any, canvas: Any, x: float, y: float, *args: Any, **kwargs: Any) -> None:
        seen.append((drawing.width, drawing.height, x, y))
        real(drawing, canvas, x, y, *args, **kwargs)

    monkeypatch.setattr(pdf_module.renderPDF, "draw", spy)
    render_invoice_pdf(invoice)
    ((width, height, x, y),) = seen
    page_width, page_height = A4
    assert math.isclose(width, 35 * mm) and math.isclose(height, 35 * mm)
    assert math.isclose(x + width / 2, page_width / 2)  # centrado
    assert page_height - (y + height) < 20 * mm  # arriba: a menos de 2 cm del borde superior
    assert y > page_height / 2


def test_the_qr_encodes_the_invoices_own_data_not_the_profile_of_now() -> None:
    """El texto del QR sale del NIF y del total de la fila de la factura: otra fila, otro QR."""
    a = qr_payload(pdf_invoice().issuer_tax_id, "2026-001", date(2026, 3, 2), 127_200)
    b = qr_payload(pdf_invoice(issuer_tax_id="01230956L").issuer_tax_id, "2026-001", date(2026, 3, 2), 127_200)
    assert a != b
    assert render_invoice_pdf(pdf_invoice()) != render_invoice_pdf(pdf_invoice(issuer_tax_id="01230956L"))


@pytest.mark.parametrize(
    "invoice", [pdf_invoice(), rectifying(), pdf_invoice(issuer_tax_id="01230956L", total_cents=5)]
)
def test_the_pdf_encodes_the_issuer_nif_the_number_the_date_and_the_signed_total(
    monkeypatch: pytest.MonkeyPatch, invoice: Any
) -> None:
    """El texto que el PDF mete en el QR sale de la fila de la factura: NIF del emisor, número, fecha y TOTAL con su signo (no la base)."""
    seen: list[str] = []
    real = pdf_module.qr_widget

    def spy(payload: str) -> Any:
        seen.append(payload)
        return real(payload)

    monkeypatch.setattr(pdf_module, "qr_widget", spy)
    render_invoice_pdf(invoice)
    assert seen == [qr_payload(invoice.issuer_tax_id, invoice.display_number, invoice.issue_date, invoice.total_cents)]
