"""Clientes: crear, editar, archivar y listar (SPEC-W-006 §5.3). Solo el rol `usuario`.

El ámbito y el estado de VIES (simulado, sin red) los calcula el servidor; la persona escribe el nombre, el tipo, el país, el NIF o NIF-IVA y el
domicilio. Un cliente no se borra: se archiva.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from cuadre.clients.models import ArchivedInput, Client, ClientInput
from cuadre.clients.service import ClientService
from cuadre.clients.vies import ViesChecker
from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router

router = new_router(tags=["clientes"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_client_service(request: Request) -> ClientService:
    state = request.app.state
    checker: ViesChecker = state.vies_checker
    return ClientService(state.db_pool, checker)


Service = Annotated[ClientService, Depends(get_client_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar clientes (solo `usuario`) o la cuenta está suspendida",
        404: "El cliente no existe (también si es de otra persona)",
        409: "Ya hay otro cliente activo con ese identificador fiscal, o el cliente está archivado",
        422: "Datos no válidos (`fields` enumera todos los campos que fallan)",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


@router.get(
    "/api/clients",
    operation_id="list_clients",
    response_model=list[Client],
    summary="Listar los clientes por nombre (los archivados solo con `include_archived`)",
    responses=problems(401, 403),
)
def list_clients(user: Usuario, service: Service, include_archived: bool = False) -> list[Client]:
    return service.list_clients(user, include_archived)


@router.get(
    "/api/clients/{client_id}",
    operation_id="get_client",
    response_model=Client,
    summary="Obtener un cliente",
    responses=problems(401, 403, 404),
)
def get_client(client_id: UUID, user: Usuario, service: Service) -> Client:
    return service.get_client(user, client_id)


@router.post(
    "/api/clients",
    operation_id="create_client",
    status_code=201,
    response_model=Client,
    summary="Crear un cliente (todo o nada, con todos los errores a la vez)",
    responses=problems(401, 403, 409, 422),
)
def create_client(body: ClientInput, user: Usuario, service: Service) -> Client:
    return service.create_client(user, body)


@router.put(
    "/api/clients/{client_id}",
    operation_id="update_client",
    response_model=Client,
    summary="Sustituir los datos de un cliente activo",
    responses=problems(401, 403, 404, 409, 422),
)
def update_client(client_id: UUID, body: ClientInput, user: Usuario, service: Service) -> Client:
    return service.update_client(user, client_id, body)


@router.put(
    "/api/clients/{client_id}/archived",
    operation_id="set_client_archived",
    response_model=Client,
    summary="Archivar o reactivar un cliente (no se borra)",
    responses=problems(401, 403, 404, 409),
)
def set_client_archived(client_id: UUID, body: ArchivedInput, user: Usuario, service: Service) -> Client:
    return service.set_client_archived(user, client_id, body.archived)
