"""Contenido del QR de VeriFactu **simulado** (SPEC-W-007 D-11, RES-04, B.1-B). Python puro; el dibujo del QR es del hito 4.

Lleva los cuatro datos del QR real de la AEAT (NIF del emisor, serie y número, fecha de expedición e importe total) **con sus formatos**: fecha
`DD-MM-AAAA` e importe con punto decimal, con signo en una rectificativa. No es una URL: no apunta al servicio de cotejo y escanearlo no
consulta nada. Nunca `float`: el importe se escribe desde céntimos enteros.
"""

from datetime import date

from cuadre.invoicing.limits import QR_PREFIX, QR_SEPARATOR


def format_qr_amount(total_cents: int) -> str:
    """`127200` → `1272.00`, `-21200` → `-212.00`, `0` → `0.00`."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("El importe va en céntimos enteros.")
    sign = "-" if total_cents < 0 else ""
    units, cents = divmod(abs(total_cents), 100)
    return f"{sign}{units}.{cents:02d}"


def format_qr_date(issue_date: date) -> str:
    return f"{issue_date.day:02d}-{issue_date.month:02d}-{issue_date.year:04d}"


def qr_payload(nif: str, display_number: str, issue_date: date, total_cents: int) -> str:
    """`CUADRE-VERIFACTU-SIMULADO|{NIF}|{serie}-{NNN}|{DD-MM-AAAA}|{importe}`. Un campo vacío o con el separador sería un QR ambiguo."""
    for name, value in (("NIF", nif), ("número", display_number)):
        if not value or QR_SEPARATOR in value:
            raise ValueError(f"El {name} no puede estar vacío ni llevar «{QR_SEPARATOR}».")
    return QR_SEPARATOR.join(
        (QR_PREFIX, nif, display_number, format_qr_date(issue_date), format_qr_amount(total_cents))
    )
