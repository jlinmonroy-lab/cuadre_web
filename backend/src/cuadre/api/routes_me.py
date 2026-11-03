"""La cuenta de quien hace la petición."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel

from cuadre.core.auth import CurrentUser, get_current_user
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router

router = new_router(tags=["cuenta"])


class MeResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: Literal["usuario", "gestor", "admin"]
    status: Literal["active"]


@router.get(
    "/api/me",
    operation_id="get_me",
    response_model=MeResponse,
    summary="Obtener la cuenta autenticada y su rol",
    responses={
        401: {"model": ProblemDetails, "description": "Sin sesión, o sesión inválida o caducada"},
        403: {"model": ProblemDetails, "description": "Cuenta suspendida o sin perfil"},
        503: {"model": ProblemDetails, "description": "No se puede comprobar la sesión ahora mismo"},
    },
)
def get_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status="active",
    )
