"""Textos de la factura que no dependen de ningún idioma del sistema (SPEC-W-007 §5.1.6). Python puro, sin `locale`."""

import unicodedata
from datetime import date
from decimal import Decimal

MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def long_date(value: date) -> str:
    """`3 de noviembre de 2026`."""
    return f"{value.day} de {MONTHS[value.month - 1]} de {value.year}"


def numeric_date(value: date) -> str:
    """`03/11/2026`, para los mensajes."""
    return f"{value.day:02d}/{value.month:02d}/{value.year:04d}"


def rectification_reference(display_number: str, issue_date: date) -> str:
    """La línea con que una rectificativa identifica la factura que rectifica (art. 15.4 del Reglamento)."""
    return f"Factura rectificativa de la {display_number} de {long_date(issue_date)}"


def format_euros(cents: int) -> str:
    """`120000` → `1.200,00 €`, `-21200` → `-212,00 €`, `5` → `0,05 €`: miles con punto y decimales con coma, desde céntimos enteros (sin `float` ni `locale`)."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise ValueError("El importe va en céntimos enteros.")
    units, rest = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}{units:,}".replace(",", ".") + f",{rest:02d} €"


# Letras latinas que no se descomponen en una letra y un signo y que Helvetica (WinAnsi) no tiene.
_TRANSLITERATE = {
    "Ł": "L",
    "ł": "l",
    "Đ": "D",
    "đ": "d",
    "Ħ": "H",
    "ħ": "h",
    "ı": "i",
    "ĸ": "k",
    "Ŀ": "L",
    "ŀ": "l",
    "Ŧ": "T",
    "ŧ": "t",
}


def _fits_winansi(char: str) -> bool:
    try:
        char.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


def pdf_text(text: str) -> str:
    """El texto tal como lo dibuja Helvetica (WinAnsi). `reportlab` NO falla con una letra que la fuente no tiene: dibuja un cuadrado negro. Aquí lo
    que cabe en cp1252 (`ñ`, `€`, acentos…) pasa tal cual; el resto se baja a su letra sin signo (`ş` → `s`, `ł` → `l`) y lo que aun así no cabe
    (cirílico, chino, emoji) se escribe `?`. Los controles y los saltos de línea se quedan fuera: el dibujo parte las líneas él."""
    out: list[str] = []
    for char in text:
        if unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp"}:
            out.append(" " if char in "\n\r\t" else "")
        elif _fits_winansi(char):
            out.append(char)
        else:
            plain = _TRANSLITERATE.get(char) or unicodedata.normalize("NFKD", char)[:1]
            out.append(plain if plain and plain.isascii() else "?")
    return "".join(out)


def format_percent(rate: Decimal) -> str:
    """`Decimal('21.00')` → `21 %`, `Decimal('7.5')` → `7,5 %`: sin ceros de más y con coma decimal."""
    return f"{rate.normalize():f}".replace(".", ",") + " %"


def format_iban(iban: str) -> str:
    """El IBAN en grupos de cuatro para leerlo (`ES36 0000 0000 0500 0000 0001`)."""
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
