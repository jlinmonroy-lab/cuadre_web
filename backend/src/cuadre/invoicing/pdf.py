"""El PDF de una factura, con su QR simulado (SPEC-W-007 §5.1.6, D-03, D-10, D-11, T7-09, T7-10).

Dibuja con `reportlab` (Helvetica, que cubre `€`, `ñ` y los acentos sin empaquetar una fuente) y `Pillow` (solo para leer el logo). **Determinista**:
`Canvas(invariant=1)` fija la fecha de creación y los identificadores, y los metadatos son fijos y sin datos personales; los mismos datos dan los
mismos bytes dentro de un mismo entorno (B.1-A midió idénticos Windows y Linux con la misma `zlib`). Por eso la huella SHA-256 guardada es la que
manda al descargar y no se regenera el PDF para compararlo.

Este módulo no toca la base de datos ni la red (T7-09): recibe los datos ya leídos y, a lo sumo, los bytes del logo. Las letras que Helvetica no
tiene se bajan con `pdf_text` antes de dibujarlas (`reportlab` no falla: pinta un cuadrado negro).

El QR va arriba y centrado, de 35 mm (zona de silencio incluida), de nivel M, con el texto simulado de `qr_payload` y debajo su leyenda: no es una
URL ni consulta nada. Una factura cabe en una página A4 con los límites de la spec (concepto y motivo de 300 caracteres, domicilios de 300).
"""

import io
from decimal import Decimal
from typing import SupportsFloat

from PIL import Image
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen.canvas import Canvas

from cuadre.invoicing.limits import QR_CAPTION, QR_LEVEL, QR_SIZE_MM
from cuadre.invoicing.logo import logo_fits
from cuadre.invoicing.qr import qr_payload
from cuadre.invoicing.texts import (
    format_euros,
    format_iban,
    format_percent,
    long_date,
    pdf_text,
    rectification_reference,
)
from cuadre.invoicing.types import PdfInvoice

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
COLUMN_WIDTH = 80 * mm
CLIENT_X = PAGE_WIDTH - MARGIN - COLUMN_WIDTH
LOGO_BOX = (50 * mm, 20 * mm)  # ancho y alto máximos; arriba a la izquierda, sin tocar el QR (que va centrado)
LOGO_FORMATS = {"PNG", "JPEG", "WEBP"}
FONT, BOLD = "Helvetica", "Helvetica-Bold"
CREATOR = "cuadre-web"
GRAY = 35  # por ciento de negro: la geometría del dibujo va en enteros (milímetros y puntos), sin literales decimales (RES-02)


def qr_widget(payload: str) -> QrCodeWidget:
    """El QR de nivel M de `QR_SIZE_MM` milímetros por lado (con su zona de silencio)."""
    size = QR_SIZE_MM * mm
    return QrCodeWidget(payload, barLevel=QR_LEVEL, barWidth=size, barHeight=size)


def logo_image(data: bytes | None) -> ImageReader | None:
    """El logo listo para dibujar, o `None` si no hay, no es PNG/JPEG/WebP, mide más de 4 Mpx o no se entiende. Las dimensiones se leen **sin
    decodificar los píxeles** (`Image.open(...).size`): un PNG de 269 KiB puede costar 872 MiB al dibujarlo (B.1-A)."""
    if not data:
        return None
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in LOGO_FORMATS or not logo_fits(*image.size):
                return None
        return ImageReader(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - un logo ilegible no impide emitir: la factura sale sin él
        return None


class _Page:
    """El lienzo con un cursor vertical en milímetros desde arriba: cada bloque escribe y baja."""

    def __init__(self, canvas: Canvas, y_mm: SupportsFloat) -> None:
        self.c = canvas
        self.y = y_mm

    def line(
        self,
        text: str,
        x: SupportsFloat,
        *,
        font: str = FONT,
        size: int = 10,
        gray: int = 0,
        right: bool = False,
        step: int = 5,
    ) -> None:
        self.c.setFont(font, size)
        self.c.setFillGray(gray / 100)
        baseline = PAGE_HEIGHT - self.y * mm
        if right:
            self.c.drawRightString(x, baseline, pdf_text(text))
        else:
            self.c.drawString(x, baseline, pdf_text(text))
        self.y += step

    def paragraph(
        self, text: str, x: SupportsFloat, width: SupportsFloat, *, font: str = FONT, size: int = 10, gray: int = 0
    ) -> None:
        for chunk in text.split("\n"):
            for row in simpleSplit(pdf_text(chunk), font, size, width) or [""]:
                self.line(row, x, font=font, size=size, gray=gray)


def _draw_logo(canvas: Canvas, logo: ImageReader | None) -> None:
    if logo is None:
        return
    box_w, box_h = LOGO_BOX
    try:
        canvas.drawImage(
            logo,
            MARGIN,
            PAGE_HEIGHT - 12 * mm - box_h,
            width=box_w,
            height=box_h,
            preserveAspectRatio=True,
            anchor="nw",
            mask="auto",
        )
    except Exception:  # noqa: BLE001 - se decodifica aquí; si falla, sin logo
        return


def _draw_qr(canvas: Canvas, invoice: PdfInvoice) -> SupportsFloat:
    """Arriba y centrado; devuelve la posición vertical (mm desde arriba) donde acaba la leyenda."""
    size = QR_SIZE_MM * mm
    widget = qr_widget(
        qr_payload(invoice.issuer_tax_id, invoice.display_number, invoice.issue_date, invoice.total_cents)
    )
    drawing = Drawing(size, size)
    drawing.add(widget)
    top = 12 * mm
    renderPDF.draw(drawing, canvas, (PAGE_WIDTH - size) / 2, PAGE_HEIGHT - top - size)
    canvas.setFont(FONT, 7)
    canvas.setFillGray(GRAY / 100)
    canvas.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - top - size - 4 * mm, QR_CAPTION)
    return (top + size) / mm + 7


def _amount_rows(invoice: PdfInvoice) -> list[tuple[str, str]]:
    """Base, IVA (con su tipo o «Sin IVA»), retención si la hay (resta, así que se ve con el signo contrario) y total."""
    rows = [("Base imponible", format_euros(invoice.base_cents))]
    if invoice.vat_rate == Decimal(0):
        rows.append(("Sin IVA", format_euros(0)))
    else:
        rows.append((f"IVA ({format_percent(invoice.vat_rate)})", format_euros(invoice.vat_cents)))
    if invoice.irpf_rate != Decimal(0):
        rows.append((f"Retención IRPF ({format_percent(invoice.irpf_rate)})", format_euros(-invoice.irpf_cents)))
    return rows


def render_invoice_pdf(invoice: PdfInvoice, logo: bytes | None = None) -> bytes:
    """Los bytes del PDF de una factura o rectificativa. Mismos datos, mismos bytes."""
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4, invariant=1, pageCompression=1)
    canvas.setTitle(pdf_text(f"Factura {invoice.display_number}"))
    canvas.setAuthor(CREATOR)
    canvas.setCreator(CREATOR)
    canvas.setSubject("Factura emitida con cuadre-web")

    _draw_logo(canvas, logo_image(logo))
    page = _Page(canvas, _draw_qr(canvas, invoice))

    # --- Título y fecha -------------------------------------------------------------------------------------------------
    rectifying = invoice.kind == "rectifying"
    page.y += 6
    top = page.y
    page.line("FACTURA RECTIFICATIVA" if rectifying else "FACTURA", MARGIN, font=BOLD, size=16, step=7)
    page.line(f"Número {invoice.display_number}", MARGIN, font=BOLD, size=11)
    page.y = top
    page.line("Fecha de expedición", PAGE_WIDTH - MARGIN, size=8, gray=GRAY, right=True, step=4)
    page.line(long_date(invoice.issue_date), PAGE_WIDTH - MARGIN, font=BOLD, size=11, right=True)
    page.y = top + 20

    # --- Emisor y cliente (copias de la fila) --------------------------------------------------------------------------------
    start = page.y
    page.line("EMISOR", MARGIN, font=BOLD, size=8, gray=GRAY)
    page.line(invoice.issuer_name, MARGIN, font=BOLD, size=11)
    page.line(f"NIF: {invoice.issuer_tax_id}", MARGIN)
    page.paragraph(invoice.issuer_address, MARGIN, COLUMN_WIDTH)
    after_issuer = page.y
    page.y = start
    page.line("CLIENTE", CLIENT_X, font=BOLD, size=8, gray=GRAY)
    page.line(invoice.client_name, CLIENT_X, font=BOLD, size=11)
    if invoice.client_tax_id:
        page.line(f"NIF/NIF-IVA: {invoice.client_tax_id}", CLIENT_X)
    page.paragraph(invoice.client_address, CLIENT_X, COLUMN_WIDTH)
    page.y = max(page.y, after_issuer) + 6

    # --- La factura que se rectifica ---------------------------------------------------------------------------------------
    if rectifying and invoice.rectifies_number is not None and invoice.rectifies_date is not None:
        page.paragraph(
            rectification_reference(invoice.rectifies_number, invoice.rectifies_date), MARGIN, CONTENT_WIDTH, font=BOLD
        )
        if invoice.rectification_reason:
            page.paragraph(f"Motivo: {invoice.rectification_reason}", MARGIN, CONTENT_WIDTH)
        page.y += 4

    # --- Concepto ----------------------------------------------------------------------------------------------------------
    page.line("CONCEPTO", MARGIN, font=BOLD, size=8, gray=GRAY)
    page.paragraph(invoice.concept, MARGIN, CONTENT_WIDTH)
    page.y += 6

    # --- Importes ----------------------------------------------------------------------------------------------------------
    label_x, value_x = PAGE_WIDTH - MARGIN - 78 * mm, PAGE_WIDTH - MARGIN
    for label, value in _amount_rows(invoice):
        page.line(label, label_x)
        page.y -= 5
        page.line(value, value_x, right=True)
    canvas.setStrokeGray(GRAY / 100)
    canvas.line(label_x, PAGE_HEIGHT - (page.y - 2) * mm, value_x, PAGE_HEIGHT - (page.y - 2) * mm)
    page.y += 2
    page.line("TOTAL", label_x, font=BOLD, size=11, step=0)
    page.line(format_euros(invoice.total_cents), value_x, font=BOLD, size=11, right=True, step=8)

    # --- Mención legal e IBAN --------------------------------------------------------------------------------------------
    if invoice.legal_note:
        page.paragraph(invoice.legal_note, MARGIN, CONTENT_WIDTH, font=BOLD, size=9)
        page.y += 3
    if invoice.issuer_iban:
        page.paragraph(f"Forma de pago: transferencia a {format_iban(invoice.issuer_iban)}", MARGIN, CONTENT_WIDTH)

    # --- Pie ---------------------------------------------------------------------------------------------------------------
    canvas.setFont(FONT, 7)
    canvas.setFillGray(GRAY / 100)
    canvas.drawCentredString(
        PAGE_WIDTH / 2, 10 * mm, "Documento generado con cuadre-web. Proyecto de demostración: no se remite a la AEAT."
    )
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()
