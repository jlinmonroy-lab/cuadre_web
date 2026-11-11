"""Modelos de la API del borrador del modelo 303 (SPEC-W-008 §5.1 y §5.3). De ellos sale el cliente TypeScript.

Solo salida: no hay cuerpo de petición. El dominio (`cuadre.tax`) devuelve dataclasses sin Pydantic y `present` las pasa a estos modelos.
Importes siempre `int` de céntimos con signo (RES-02); las fechas son ISO. Todo se calcula en el servidor: la interfaz no suma nada.
"""

from datetime import date as Day
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cuadre.tax import Modelo303 as Draft303

BoxGroup = Literal["devengado", "deducible", "resultado", "adicional"]
DeadlineStatus = Literal["en_curso", "plazo_abierto", "plazo_cerrado"]
ResultKind = Literal["a_ingresar", "a_compensar", "a_cero", "sin_actividad"]


class Item303(BaseModel):
    """Un documento que compone una casilla, con lo que aporta (negativo en una rectificativa)."""

    kind: Literal["invoice", "expense"] = Field(description="Factura emitida o gasto registrado")
    id: UUID
    label: str = Field(description="Número de factura o proveedor del gasto")
    date: Day = Field(description="Fecha de expedición de la factura o del gasto")
    base_cents: int
    vat_cents: int


class Box303(BaseModel):
    """Una casilla del modelo 303. Las derivadas (27, 45 y 46) no llevan documentos: enumeran en `components` las casillas que las componen."""

    code: str = Field(description="Número de casilla: 01, 03, 04, 06, 07, 09, 27, 28, 29, 45, 46, 59 o 120")
    label: str
    group: BoxGroup
    measure: Literal["base", "vat"] | None = Field(
        description="Qué importe de cada documento suma en la casilla; `null` en las derivadas"
    )
    amount_cents: int = Field(description="Importe de la casilla, en céntimos y con signo")
    items: list[Item303] = Field(
        description="Los documentos que la componen, por fecha; su suma (según `measure`) es la casilla"
    )
    components: list[str] = Field(description="Casillas que componen una derivada; vacío en las demás")


class Modelo303(BaseModel):
    """El borrador orientativo del 303 de un trimestre natural. No se presenta ante la AEAT desde la aplicación."""

    year: int
    quarter: int = Field(description="1 a 4")
    period_start: Day = Field(description="Primer día del trimestre")
    period_end: Day = Field(description="Primer día del trimestre siguiente (el final es exclusivo)")
    deadline: Day = Field(
        description="Último día de presentación según el calendario (la AEAT lo traslada si cae en un día inhábil)"
    )
    deadline_status: DeadlineStatus
    boxes: list[Box303] = Field(description="Siempre las trece casillas, en el orden de la pantalla, también a cero")
    result_cents: int = Field(description="Casilla 46: 27 − 45")
    result_kind: ResultKind = Field(
        description="`a_cero` si hay documentos pero el resultado es 0; `sin_actividad` solo si el trimestre no tiene ningún documento"
    )
    notes: list[str] = Field(
        description="Avisos fijos: orientativo, lo que no incluye, Canarias, Ceuta y Melilla y, con la casilla 59, el modelo 349"
    )


def present(model: Draft303) -> Modelo303:
    """El borrador del dominio, como modelo de la API."""
    return Modelo303(
        year=model.year,
        quarter=model.quarter,
        period_start=model.period_start,
        period_end=model.period_end,
        deadline=model.deadline,
        deadline_status=model.deadline_status,
        boxes=[
            Box303(
                code=box.code,
                label=box.label,
                group=box.group,
                measure=box.measure,
                amount_cents=box.amount_cents,
                items=[
                    Item303(
                        kind=item.kind,
                        id=UUID(item.id),
                        label=item.label,
                        date=item.date,
                        base_cents=item.base_cents,
                        vat_cents=item.vat_cents,
                    )
                    for item in box.items
                ],
                components=list(box.components),
            )
            for box in model.boxes
        ],
        result_cents=model.result_cents,
        result_kind=model.result_kind,
        notes=list(model.notes),
    )
