"""Modelos de la API de clientes (SPEC-W-006 §5.3). De ellos sale el cliente TypeScript.

La **entrada es suelta** (Anexo B.1-D): `str` con `max_length`, sin `Literal` ni patrón y con `extra="forbid"`. Si el tipo o el país se
declararan con `Literal` o un patrón, Pydantic respondería un `validation_error` por separado y no se devolverían **todos los errores a la vez**;
el contenido lo valida `cuadre.clients`. El ámbito y el estado de VIES NO se envían: los calcula el dominio. La salida sí lleva uniones de
literales para el cliente generado.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ClientInput(BaseModel):
    """Los campos de §5.1. Los ausentes valen `null` y el dominio dice cuáles hacen falta."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=1000)
    kind: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=2000)


class ArchivedInput(BaseModel):
    """`archived` va con `StrictBool`: un `"yes"` no es `true` (B.1-D)."""

    model_config = ConfigDict(extra="forbid")

    archived: StrictBool


class Client(BaseModel):
    id: UUID
    name: str
    kind: Literal["business", "individual"]
    country: str
    scope: Literal["national", "eu", "non_eu"]
    tax_id: str | None
    address: str | None
    vies_status: Literal["valid_simulated", "unchecked", "not_applicable"]
    archived: bool
    created_at: datetime
    updated_at: datetime
