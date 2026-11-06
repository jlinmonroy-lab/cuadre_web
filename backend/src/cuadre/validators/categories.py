"""Categorías de gasto y sugerencia por palabras clave (SPEC-W-003 §5.1, D-08).

Lista cerrada de ocho. La sugerencia mira el nombre del proveedor (minúsculas, sin tildes, **inicio de palabra**) y solo puede devolver
una de las ocho: el texto del proveedor no se interpreta. No interviene ningún modelo (RES-01). Estas etiquetas son la única fuente: la
interfaz y la herramienta MCP `gastos_por_categoria` salen de aquí.
"""

import re
import unicodedata
from enum import StrEnum


class ExpenseCategory(StrEnum):
    software = "software"
    workspace = "workspace"
    supplies = "supplies"
    utilities = "utilities"
    advisory = "advisory"
    self_employed_fee = "self_employed_fee"
    training = "training"
    other = "other"


LABELS: dict[ExpenseCategory, str] = {
    ExpenseCategory.software: "Software",
    ExpenseCategory.workspace: "Coworking y oficina",
    ExpenseCategory.supplies: "Material",
    ExpenseCategory.utilities: "Suministros y teléfono",
    ExpenseCategory.advisory: "Asesoría",
    ExpenseCategory.self_employed_fee: "Cuota de autónomos",
    ExpenseCategory.training: "Formación",
    ExpenseCategory.other: "Otros",
}

# El orden es la prioridad (el de la rutina del prototipo). `self_employed_fee`, `training` y `other` no tienen palabras clave.
KEYWORDS: tuple[tuple[ExpenseCategory, tuple[str, ...]], ...] = (
    (ExpenseCategory.software, ("soft", "nube", "cloud", "app")),
    (ExpenseCategory.supplies, ("papeler", "imprenta", "material")),
    (ExpenseCategory.workspace, ("cowork", "espacio", "oficina")),
    (ExpenseCategory.utilities, ("telef", "fibra", "luz", "energ")),
    (ExpenseCategory.advisory, ("gestor", "asesor")),
)

_WORDS = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return _WORDS.findall("".join(ch for ch in decomposed if not unicodedata.combining(ch)))


def suggest_category(supplier_name: str | None) -> ExpenseCategory:
    """La categoría sugerida para un proveedor; `other` si ninguna palabra clave coincide con el inicio de una palabra del nombre."""
    if not supplier_name:
        return ExpenseCategory.other
    words = _words(supplier_name)
    for category, prefixes in KEYWORDS:
        if any(word.startswith(prefix) for word in words for prefix in prefixes):
            return category
    return ExpenseCategory.other
