"""Modelos de la API de la contabilidad mensual (SPEC-W-012 §5.3). De ellos sale el cliente TypeScript.

Todos los importes son céntimos enteros (RES-02). La interfaz muestra estas cifras tal cual: no suma ni decide nada.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MonthStatus = Literal["closed", "in_progress", "pending"]
ClientScope = Literal["national", "eu", "non_eu"]


class ClientTotalsOut(BaseModel):
    client_id: str
    name: str = Field(description="El nombre del cliente en su última factura del mes")
    scope: ClientScope
    base_cents: int = Field(
        description="Base imponible facturada al cliente en ese ámbito durante el mes, con las rectificativas con su signo"
    )
    invoice_count: int = Field(
        ge=0, description="Facturas ordinarias (las rectificativas ajustan el importe pero no cuentan)"
    )


class MonthRow(BaseModel):
    month: int = Field(ge=1, le=12)
    status: MonthStatus = Field(
        description=(
            "`closed`: hay cierre y se devuelve su foto. `in_progress`: es el mes de hoy (cifras en vivo). "
            "`pending`: terminó y aún no hay cierre (cifras en vivo, a la espera de la siguiente ejecución del job)"
        )
    )
    invoice_count: int = Field(ge=0)
    national_cents: int
    eu_cents: int
    non_eu_cents: int
    total_cents: int = Field(description="Bases imponibles del mes, sin IVA: nacional + UE + fuera de la UE")
    expenses_cents: int = Field(description="Gastos no anulados del mes: base más IVA no deducible")
    result_cents: int = Field(
        description="Rendimiento del mes: ingresos (`total_cents`) menos gastos (`expenses_cents`)"
    )
    ytd_cents: int = Field(description="Acumulado del año hasta este mes, incluido: derivado, nunca guardado")
    revision: int | None = Field(
        description="Solo en los cerrados: 1 al cerrar y +1 cada vez que un recálculo cambia algo (documento atrasado)"
    )
    closed_at: datetime | None = Field(description="Solo en los cerrados: cuándo se guardó la última foto")


class YearTotals(BaseModel):
    invoice_count: int
    national_cents: int
    eu_cents: int
    non_eu_cents: int
    total_cents: int
    expenses_cents: int


class MonthlyClosings(BaseModel):
    year: int
    months: list[MonthRow] = Field(
        description="Desde el primer mes con actividad hasta el mes en curso (año actual) o diciembre; vacío si el año es anterior a la actividad"
    )
    totals: YearTotals = Field(description="Suma de los meses que salen en la lista")


class MonthlyClosing(MonthRow):
    year: int
    by_client: list[ClientTotalsOut] = Field(description="Ingresos por cliente y ámbito, de mayor a menor base")
