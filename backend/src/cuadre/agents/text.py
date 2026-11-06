"""Limpieza de textos que vienen de una fuente no confiable (SPEC-W-002 §5.3, T2-05).

Se muestran siempre como texto (nunca HTML); aquí solo se quita lo que no debería estar en un texto visible y se acota la longitud.
"""

import unicodedata

# Categorías Unicode que se eliminan: control (Cc), formato (Cf: ancho cero y controles bidireccionales, que sirven para
# suplantar texto) y sustitutos sueltos (Cs, que PostgreSQL no admite). Los espacios y saltos de línea se colapsan antes.
_DROPPED_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})


class InvalidText(ValueError):
    """El valor no es una cadena."""


def clean_text(value: str | None, limit: int) -> str | None:
    """Quita caracteres de control y de formato, colapsa espacios y recorta a `limit`. Lo vacío pasa a `None`."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidText
    kept = "".join(
        " " if ch.isspace() else ch
        for ch in unicodedata.normalize("NFC", value)
        if ch.isspace() or unicodedata.category(ch) not in _DROPPED_CATEGORIES
    )
    return " ".join(kept.split())[:limit].rstrip() or None
