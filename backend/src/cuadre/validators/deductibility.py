"""Deducibilidad del IVA (SPEC-W-003 §5.1, D-06). **Orientativa**: no decide gastos de deducción limitada (vehículo, vivienda afecta,
atenciones). Siempre devuelve su motivo, que la persona ve junto al gasto.
"""

from dataclasses import dataclass
from typing import Literal

from cuadre.validators.tax_id import normalize_tax_id

EU_NOTE = "El IVA de un proveedor de la UE no se deduce en el 303 de Cuadre; el gasto cuenta en el 130."


@dataclass(frozen=True, slots=True)
class Deductibility:
    deductible: bool
    note: str


def deductible_vat(
    doc_type: str | None,
    scope: Literal["national", "eu"] | None,
    vat_cents: int | None,
    recipient_tax_id: str | None,
    owner_tax_id: str | None,
) -> Deductibility:
    """Falso si el proveedor es de la UE o si no hay cuota. Verdadero para una factura completa. Para una simplificada o un ticket, solo si el
    NIF del destinatario, normalizado, es el del perfil y no está vacío. Falso para un recibo y para cualquier otro tipo."""
    if scope == "eu":
        return Deductibility(False, EU_NOTE)
    if not vat_cents:  # None o 0
        return Deductibility(False, "No hay cuota de IVA que deducir.")
    if doc_type == "full_invoice":
        return Deductibility(
            True, "Factura completa de un proveedor español con IVA: el IVA es deducible (orientativo)."
        )
    if doc_type in ("simplified_invoice", "ticket"):
        recipient = normalize_tax_id(recipient_tax_id)
        owner = normalize_tax_id(owner_tax_id)
        if recipient is not None and owner is not None and recipient.key == owner.key:
            return Deductibility(True, "Factura simplificada con tu NIF: el IVA es deducible (orientativo).")
        return Deductibility(False, "Factura simplificada: el IVA solo se deduce si lleva tu NIF.")
    return Deductibility(False, "Este tipo de documento no da derecho a deducir el IVA.")
