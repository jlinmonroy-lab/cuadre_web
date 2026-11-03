"""Comprobación de vida. No toca la base de datos: sirve para que la plataforma sepa si el proceso responde."""

from typing import Literal

from pydantic import BaseModel

from cuadre import __version__
from cuadre.core.routing import new_router

router = new_router(tags=["sistema"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get(
    "/healthz", operation_id="get_health", response_model=HealthResponse, summary="Comprobar que la API responde"
)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
