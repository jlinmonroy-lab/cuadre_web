"""Tipos comunes de los contratos de Cuadre.

Regla de oro (RES-02): ningún campo de ningún contrato es `float`. Los importes viajan como
cadenas decimales (`"120.00"`) y las cifras agregadas del MCP como céntimos enteros.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Amount = Annotated[
    str,
    StringConstraints(pattern=r"^-?\d{1,12}\.\d{2}$"),
    Field(description="Importe en euros como cadena decimal con punto y dos decimales.", examples=["120.00"]),
]

Rate = Annotated[
    str,
    StringConstraints(pattern=r"^\d{1,3}(\.\d{1,2})?$"),
    Field(description="Porcentaje como cadena decimal, sin el signo %.", examples=["21", "7.5"]),
]

Cost = Annotated[
    str,
    StringConstraints(pattern=r"^\d{1,6}\.\d{2,6}$"),
    Field(description="Coste en euros como cadena decimal (hasta seis decimales).", examples=["0.004200"]),
]

Currency = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{3}$"),
    Field(description="Código de moneda ISO 4217.", examples=["EUR"]),
]

Locale = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z]{2}-[A-Z]{2}$"),
    Field(description="Idioma y región (BCP 47 reducido).", examples=["es-ES"]),
]


class ContractModel(BaseModel):
    """Base de todos los modelos: los receptores ignoran campos desconocidos.

    Es lo que permite añadir campos opcionales en una versión 1.x sin romper a nadie.
    """

    model_config = ConfigDict(extra="ignore")


class ResponseModel(ContractModel):
    """Base de lo que emite el servicio receptor: sus esquemas marcan como obligatorio
    todo campo que siempre se serializa, aunque tenga valor por defecto."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
