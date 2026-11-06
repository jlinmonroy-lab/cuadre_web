"""Importes para los mensajes: céntimos enteros a «1.234,50 €» (es-ES). Aritmética entera, sin `float` (RES-02)."""


def format_euros(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    units, remainder = divmod(abs(cents), 100)
    return f"{sign}{units:,}".replace(",", ".") + f",{remainder:02d} €"
