"""Acceso del gestor: invitar, aceptar, rechazar y revocar (SPEC-W-010 §5.3). El autónomo invita y revoca; el gestor acepta y rechaza.

Todo es una lectura o un cambio de estado con las funciones `app.*` de la base de datos (que registran su rastro en `activity_log`). Nada de lo que escribe o
lee el gestor sobre la contabilidad del autónomo está aquí: eso es del hito 2. `Cache-Control: private, no-store` en todas.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, Response

from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.gestor.models import GestorAccess, GestorInvitation, InvitedAccess, InviteInput
from cuadre.gestor.service import GestorService

router = new_router(tags=["gestor"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]
Gestor = Annotated[CurrentUser, Depends(require_role_detached("gestor"))]


def get_gestor_service(request: Request) -> GestorService:
    state = request.app.state
    return GestorService(state.db_pool, state.email_sender, state.settings.frontend_origin)


Service = Annotated[GestorService, Depends(get_gestor_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida",
        404: "El acceso o la invitación no existe (también si es de otra persona)",
        409: "La invitación o el acceso no está en el estado que esta acción necesita",
        422: "Correo no válido, invitación a uno mismo o demasiadas invitaciones abiertas",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


# --- Autónomo ---------------------------------------------------------------------------------------------------------------------


@router.post(
    "/api/gestor/accesos",
    operation_id="invite_gestor_access",
    status_code=201,
    response_model=InvitedAccess,
    summary="Invitar a un gestor por correo (la respuesta no revela si el correo es de una cuenta)",
    responses=problems(401, 403, 409, 422),
)
def invite_gestor_access(body: InviteInput, user: Usuario, service: Service, response: Response) -> InvitedAccess:
    no_store(response)
    return service.invite(user, body.email)


@router.get(
    "/api/gestor/accesos",
    operation_id="list_gestor_accesses",
    response_model=list[GestorAccess],
    summary="Los accesos e invitaciones que el autónomo ha dado, el más reciente primero",
    responses=problems(401, 403),
)
def list_gestor_accesses(user: Usuario, service: Service, response: Response) -> list[GestorAccess]:
    no_store(response)
    return service.list_accesses(user)


@router.post(
    "/api/gestor/accesos/{access_id}/revocar",
    operation_id="revoke_gestor_access",
    status_code=204,
    response_class=Response,
    summary="Revocar un acceso o retirar una invitación pendiente (el gestor pierde el acceso al instante)",
    responses=problems(401, 403, 404, 409),
)
def revoke_gestor_access(access_id: UUID, user: Usuario, service: Service) -> Response:
    service.revoke(user, access_id)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


# --- Gestor -----------------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/invitaciones",
    operation_id="list_gestor_invitations",
    response_model=list[GestorInvitation],
    summary="Las invitaciones pendientes dirigidas al gestor, con el nombre de quien invita",
    responses=problems(401, 403),
)
def list_gestor_invitations(user: Gestor, service: Service, response: Response) -> list[GestorInvitation]:
    no_store(response)
    return service.list_invitations(user)


@router.post(
    "/api/gestor/invitaciones/{access_id}/aceptar",
    operation_id="accept_gestor_invitation",
    status_code=204,
    response_class=Response,
    summary="Aceptar una invitación dirigida al correo del gestor",
    responses=problems(401, 403, 404, 409),
)
def accept_gestor_invitation(access_id: UUID, user: Gestor, service: Service) -> Response:
    service.accept(user, access_id)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.post(
    "/api/gestor/invitaciones/{access_id}/rechazar",
    operation_id="decline_gestor_invitation",
    status_code=204,
    response_class=Response,
    summary="Rechazar una invitación dirigida al correo del gestor",
    responses=problems(401, 403, 404, 409),
)
def decline_gestor_invitation(access_id: UUID, user: Gestor, service: Service) -> Response:
    service.decline(user, access_id)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
