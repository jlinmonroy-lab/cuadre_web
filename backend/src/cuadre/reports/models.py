"""Modelos de la API del reporte mensual (SPEC-W-013 §5.3). De ellos sale el cliente TypeScript.

Todos los importes son céntimos enteros y las variaciones y cuotas, puntos básicos enteros (RES-02). La interfaz las muestra tal cual: no suma, no compara ni redondea.
"""

from pydantic import BaseModel, Field

from cuadre.closing.models import ClientScope, MonthlyClosing, MonthStatus
from cuadre.validators.categories import ExpenseCategory


class ScopeShareOut(BaseModel):
    scope: ClientScope
    base_cents: int = Field(
        description="Base imponible facturada en ese ámbito durante el mes, con las rectificativas con su signo"
    )
    share_bp: int | None = Field(
        description=(
            "Cuota sobre el total del mes en puntos básicos (1 pb = 0,01 %), con redondeo half-up; `null` si el total no es mayor que 0 "
            "o la base es negativa. Las tres cuotas pueden no sumar exactamente 10 000"
        )
    )


class CategoryTotalOut(BaseModel):
    category: ExpenseCategory
    label: str = Field(description="El nombre de la categoría en español, único origen: `validators.categories`")
    expenses_cents: int = Field(
        description="Base más IVA no deducible de los gastos no anulados de la categoría en el mes"
    )
    expense_count: int = Field(ge=0)


class ComparisonOut(BaseModel):
    previous_year: int
    previous_month: int = Field(ge=1, le=12)
    previous_status: MonthStatus
    total_cents: int = Field(description="Los ingresos del mes anterior")
    expenses_cents: int = Field(description="Los gastos del mes anterior")
    result_cents: int = Field(description="El resultado del mes anterior: ingresos menos gastos")
    total_delta_cents: int = Field(description="Ingresos de este mes menos los del anterior")
    expenses_delta_cents: int
    result_delta_cents: int
    total_variation_bp: int | None = Field(
        description="Variación de los ingresos en puntos básicos; `null` si los del mes anterior no son mayores que 0"
    )
    expenses_variation_bp: int | None = Field(
        description="Variación de los gastos en puntos básicos; `null` si los del mes anterior no son mayores que 0"
    )


class TrendPoint(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    status: MonthStatus
    total_cents: int
    expenses_cents: int
    result_cents: int


class MonthlyReport(MonthlyClosing):
    """El mes (como en `/api/monthly-closings/{year}/{month}`) más todo lo que dibuja el reporte."""

    comparison: ComparisonOut | None = Field(
        description="Frente al mes anterior; `null` si no hay mes anterior con actividad"
    )
    scopes: list[ScopeShareOut] = Field(
        description="Los tres ámbitos, siempre en el orden nacional, UE y fuera de la UE"
    )
    expenses_by_category: list[CategoryTotalOut] = Field(
        description="Gastos por categoría calculados al leer (no son parte del cierre), de mayor a menor; solo las de importe distinto de 0"
    )
    expenses_by_category_total_cents: int = Field(description="Suma de `expenses_by_category`")
    expenses_note: str | None = Field(
        description="`null` si el desglose suma lo mismo que `expenses_cents`; si no, un aviso fijo (típicamente, un gasto registrado o anulado tras el cierre)"
    )
    trend: list[TrendPoint] = Field(
        description="Hasta 12 meses que terminan en el pedido, del más antiguo al más reciente, sin pasar de la primera actividad"
    )
    quarter: int = Field(
        ge=1, le=4, description="El trimestre natural del mes, para enlazar a los borradores del 303 y del 130"
    )
    quarter_year: int
