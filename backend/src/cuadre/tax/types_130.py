"""Tipos del modelo 130 (SPEC-W-009 §5.1). Inmutables y sin lógica: lo que entra (facturas y gastos ya leídos) y lo que sale (casillas con sus documentos).

Son tipos propios y no los del 303: el 130 necesita la retención de cada factura y el coste de cada gasto (también el de los gastos sin factura), y así el 303
no corre ningún riesgo (SPEC-W-009 D-12).
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from cuadre.tax.types_303 import DeadlineStatus

ResultKind130 = Literal["a_ingresar", "nada_que_ingresar", "sin_actividad"]
BoxGroup130 = Literal["rendimiento", "pagos", "resultado"]


@dataclass(frozen=True, slots=True)
class IncomeRow:
    """Una factura emitida. `base_cents` e `irpf_cents` llevan signo: una rectificativa lleva la diferencia. `label` es el número que se enseña."""

    id: str
    label: str
    issue_date: date
    base_cents: int
    irpf_cents: int


@dataclass(frozen=True, slots=True)
class CostRow:
    """Un gasto registrado, con factura o sin ella (los sin factura no llevan IVA). `label` es el proveedor; `voided` es `voided_at is not null`."""

    id: str
    label: str
    expense_date: date
    base_cents: int
    vat_cents: int
    deductible_vat: bool
    voided: bool


@dataclass(frozen=True, slots=True)
class Item130:
    """Un documento (o un trimestre anterior, en la casilla 05) que compone una casilla, con lo que aporta a ESA casilla, con signo."""

    kind: Literal["invoice", "expense", "quarter"]
    id: str
    label: str
    date: date
    amount_cents: int


@dataclass(frozen=True, slots=True)
class Box130:
    """Una casilla. Las derivadas (03, 04 y 07) no tienen items y enumeran en `components` las casillas que las componen."""

    code: str
    label: str
    group: BoxGroup130
    amount_cents: int
    items: tuple[Item130, ...]
    components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Modelo130:
    year: int
    quarter: int
    period_start: date  # el 1 de enero
    period_end: date  # exclusivo: el primer día del trimestre siguiente
    deadline: date
    deadline_status: DeadlineStatus
    boxes: tuple[Box130, ...]
    result_cents: int
    result_kind: ResultKind130
    withheld_share_percent: int | None
    notes: tuple[str, ...]
