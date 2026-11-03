"""Contrato 3 · Herramientas MCP de solo lectura que cuadre-web expone al chatbot.

Reglas del servidor (ver contracts/mcp/v1/README.md):
  * Solo lectura. Transacción READ ONLY con la identidad del usuario, así que se aplica la RLS.
  * Cifras ya agregadas: el modelo nunca suma ni calcula impuestos (RES-01).
  * Importes en céntimos enteros (`*_cents`), moneda siempre EUR.
  * Nunca se devuelven IBAN, domicilios ni NIF de terceros.
  * Nombres y parámetros en español, a propósito: los lee un modelo que conversa en español.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import ContractModel, ResponseModel

Ambito = Literal["nacional", "ue", "fuera_ue"]
TipoFactura = Literal["emitida", "gasto"]


class Totales(ResponseModel):
    n: int = Field(ge=0, description="Número de documentos.")
    base_cents: int
    iva_cents: int
    retencion_cents: int
    total_cents: int


class FacturaRef(ResponseModel):
    id: UUID
    tipo: TipoFactura
    numero: str | None
    contraparte: str


# --- buscar_facturas ---------------------------------------------------------------------------


class BuscarFacturasInput(ContractModel):
    tipo: Literal["emitida", "gasto", "todas"] = Field(
        default="todas", description="«emitida»: facturas del usuario a sus clientes. «gasto»: facturas de compra."
    )
    desde: date | None = Field(default=None, description="Fecha mínima (inclusive), AAAA-MM-DD.")
    hasta: date | None = Field(default=None, description="Fecha máxima (inclusive), AAAA-MM-DD.")
    cliente: str | None = Field(
        default=None, min_length=1, max_length=100, description="Texto contenido en el nombre del cliente o proveedor."
    )
    ambito: Ambito | None = Field(default=None, description="Ámbito del cliente. Solo aplica a facturas emitidas.")
    estado_cobro: Literal["cobrada", "pendiente"] | None = Field(
        default=None, description="Solo aplica a facturas emitidas."
    )
    limite: int = Field(default=20, ge=1, le=50, description="Máximo de filas devueltas; los totales cubren todas.")


class FacturaItem(ResponseModel):
    id: UUID
    tipo: TipoFactura
    numero: str | None
    fecha: date
    contraparte: str
    ambito: Ambito | None = Field(description="null en los gastos.")
    base_cents: int
    iva_cents: int
    retencion_cents: int
    total_cents: int
    cobrada: bool | None = Field(description="null en los gastos.")


class BuscarFacturasOutput(ResponseModel):
    items: list[FacturaItem]
    totales_emitidas: Totales | None = Field(description="Sobre TODAS las coincidencias, no solo las devueltas.")
    totales_gastos: Totales | None = Field(description="Sobre TODAS las coincidencias, no solo las devueltas.")
    truncado: bool = Field(description="true si hay más coincidencias que filas devueltas.")
    moneda: Literal["EUR"] = "EUR"
    as_of: datetime


# --- resumen_mes / resumen_anio ---------------------------------------------------------------


class ResumenMesInput(ContractModel):
    anio: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)


class ResumenAnioInput(ContractModel):
    anio: int = Field(ge=2000, le=2100)


class IngresosPorAmbito(ResponseModel):
    nacional_cents: int
    ue_cents: int
    fuera_ue_cents: int
    total_cents: int = Field(description="Suma de los tres ámbitos, calculada por el servidor.")


class ClienteImporte(ResponseModel):
    cliente: str
    ambito: Ambito
    base_cents: int


class ResumenPeriodoOutput(ResponseModel):
    anio: int
    mes: int | None = Field(description="null en el resumen anual.")
    estado: Literal["cerrado", "en_curso"] | None = Field(description="Estado del cierre mensual; null en el anual.")
    ingresos: IngresosPorAmbito = Field(description="Bases imponibles, sin IVA.")
    gastos_cents: int = Field(description="Gastos deducibles del periodo.")
    rendimiento_cents: int = Field(description="Ingresos menos gastos, calculado por el servidor.")
    por_cliente: list[ClienteImporte]
    acumulado_anio_cents: int
    n_facturas: int = Field(ge=0)
    moneda: Literal["EUR"] = "EUR"
    as_of: datetime


# --- borrador_trimestre -----------------------------------------------------------------------


class BorradorTrimestreInput(ContractModel):
    anio: int = Field(ge=2000, le=2100)
    trimestre: int = Field(ge=1, le=4)
    modelo: Literal["303", "130", "ambos"] = "ambos"


class Casilla(ResponseModel):
    casilla: str = Field(description="Número de casilla tal como aparece en el modelo, por ejemplo «07».")
    concepto: str
    importe_cents: int
    facturas: list[FacturaRef] = Field(description="Documentos que componen la casilla. Vacío si es un total.")


class BorradorModelo(ResponseModel):
    modelo: Literal["303", "130"]
    casillas: list[Casilla]
    resultado_cents: int = Field(description="Importe absoluto del resultado.")
    resultado_tipo: Literal["a_ingresar", "a_compensar", "cero"]


class BorradorTrimestreOutput(ResponseModel):
    anio: int
    trimestre: int
    plazo_presentacion: date
    orientativo: Literal[True] = Field(description="Siempre true: es un borrador, no se presenta ante la AEAT.")
    aviso: str
    modelos: list[BorradorModelo]
    moneda: Literal["EUR"] = "EUR"
    as_of: datetime


# --- gastos_por_categoria ---------------------------------------------------------------------


class GastosPorCategoriaInput(ContractModel):
    anio: int = Field(ge=2000, le=2100)
    mes: int | None = Field(default=None, ge=1, le=12, description="Excluyente con «trimestre».")
    trimestre: int | None = Field(default=None, ge=1, le=4, description="Excluyente con «mes».")

    @model_validator(mode="after")
    def _mes_o_trimestre(self) -> "GastosPorCategoriaInput":
        if self.mes is not None and self.trimestre is not None:
            raise ValueError("Indica «mes» o «trimestre», no ambos.")
        return self


class CategoriaImporte(ResponseModel):
    categoria: str
    base_cents: int
    iva_cents: int
    total_cents: int
    n: int = Field(ge=0)


class GastosPorCategoriaOutput(ResponseModel):
    anio: int
    mes: int | None
    trimestre: int | None
    categorias: list[CategoriaImporte]
    total: Totales
    moneda: Literal["EUR"] = "EUR"
    as_of: datetime


# --- error común ------------------------------------------------------------------------------


class ToolError(ResponseModel):
    """Contenido de un resultado MCP con isError=true."""

    code: Literal["invalid_params", "no_data", "unauthorized", "internal"]
    message: str


# --- registro ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="buscar_facturas",
        title="Buscar facturas",
        description=(
            "Busca las facturas emitidas del usuario y/o sus gastos (facturas de compra) con filtros opcionales. "
            "Devuelve las filas pedidas y los totales de TODAS las coincidencias. Úsala para preguntas como "
            "«¿cuánto he facturado a clientes de la UE este año?» (tipo=emitida, ambito=ue, desde/hasta del año) "
            "o «¿qué facturas me faltan por cobrar?» (estado_cobro=pendiente). No sumes tú las filas: usa los totales."
        ),
        input_model=BuscarFacturasInput,
        output_model=BuscarFacturasOutput,
    ),
    ToolSpec(
        name="resumen_mes",
        title="Resumen de un mes",
        description=(
            "Resumen contable de un mes: ingresos por ámbito (nacional, UE, fuera de la UE) y por cliente, gastos "
            "deducibles, rendimiento y acumulado del año. Indica si el mes ya está cerrado."
        ),
        input_model=ResumenMesInput,
        output_model=ResumenPeriodoOutput,
    ),
    ToolSpec(
        name="resumen_anio",
        title="Resumen del año",
        description=(
            "Resumen contable acumulado de un año natural: ingresos por ámbito y por cliente, gastos deducibles y "
            "rendimiento. Úsala para preguntas sobre el año completo hasta hoy."
        ),
        input_model=ResumenAnioInput,
        output_model=ResumenPeriodoOutput,
    ),
    ToolSpec(
        name="borrador_trimestre",
        title="Borrador de los modelos 303 y 130",
        description=(
            "Borrador orientativo del modelo 303 (IVA) y/o 130 (IRPF) de un trimestre, casilla a casilla y con las "
            "facturas que componen cada casilla. Es un borrador: no se presenta ante la AEAT. Explica el resultado "
            "con estas cifras; no las recalcules."
        ),
        input_model=BorradorTrimestreInput,
        output_model=BorradorTrimestreOutput,
    ),
    ToolSpec(
        name="gastos_por_categoria",
        title="Gastos por categoría",
        description=(
            "Gastos registrados agrupados por categoría (software, suministros, asesoría...) para un año, un mes "
            "o un trimestre. Indica «mes» o «trimestre», no ambos; sin ninguno, devuelve el año completo."
        ),
        input_model=GastosPorCategoriaInput,
        output_model=GastosPorCategoriaOutput,
    ),
)
