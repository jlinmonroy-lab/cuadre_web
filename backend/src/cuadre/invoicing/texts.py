"""Textos de la factura que no dependen de ningún idioma del sistema (SPEC-W-007 §5.1.6). Python puro, sin `locale`."""

from datetime import date

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
