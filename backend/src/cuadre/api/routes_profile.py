"""Perfil del negocio, logo y series de facturación (SPEC-W-005 §5.3). Solo el rol `usuario`.

El logo no pasa por la API: la persona lo sube directo a Storage con una URL firmada (ADR-0016). Aquí solo se firma y se comprueba.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from starlette.responses import Response

from cuadre.core.auth import CurrentUser, get_verified_token, require_role_detached
from cuadre.core.clock import Clock
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.documents.storage import StorageGateway
from cuadre.profile.models import (
    InvoiceSeries,
    LogoUploadRequest,
    LogoUploadResponse,
    LogoUrl,
    Profile,
    ProfileInput,
    SeriesCreate,
    SeriesUpdate,
)
from cuadre.profile.service import ProfileService

router = new_router(tags=["perfil"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]
Token = Annotated[str, Depends(get_verified_token)]


def get_profile_service(request: Request) -> ProfileService:
    state = request.app.state
    logo_storage: StorageGateway = state.logo_storage
    clock: Clock = state.clock
    return ProfileService(state.db_pool, logo_storage, clock)


Service = Annotated[ProfileService, Depends(get_profile_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida",
        404: "La serie no existe (también si es de otra persona) o no hay logo",
        409: "Código de serie en uso, serie en uso, predeterminada o archivada",
        413: "El logo supera 1 MiB",
        415: "El logo no es PNG, JPEG ni WebP",
        422: "Datos no válidos (con `fields` o `field` según el caso) o logo que no es del tipo indicado",
        503: "Almacenamiento no disponible",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


# --- Perfil -----------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/profile",
    operation_id="get_profile",
    response_model=Profile,
    summary="Leer el perfil, lo que falta para emitir y la sugerencia de retención (no escribe)",
    responses=problems(401, 403),
)
def get_profile(user: Usuario, service: Service) -> Profile:
    return service.get_profile(user)


@router.put(
    "/api/profile",
    operation_id="update_profile",
    response_model=Profile,
    summary="Guardar el perfil (todo o nada) y crear la serie del año si falta",
    responses=problems(401, 403, 422),
)
def update_profile(body: ProfileInput, user: Usuario, service: Service) -> Profile:
    return service.update_profile(user, body)


# --- Logo -------------------------------------------------------------------------------------------------------------------


@router.post(
    "/api/profile/logo",
    operation_id="upload_logo",
    status_code=201,
    response_model=LogoUploadResponse,
    summary="Reservar una subida de logo y obtener la URL firmada",
    responses=problems(401, 403, 413, 415, 422, 503),
)
def upload_logo(body: LogoUploadRequest, user: Usuario, token: Token, service: Service) -> LogoUploadResponse:
    return service.upload_logo(user, token, body)


@router.post(
    "/api/profile/logo/{upload_id}/complete",
    operation_id="complete_logo_upload",
    response_model=Profile,
    summary="Comprobar el logo subido, guardarlo y borrar el anterior",
    responses=problems(401, 403, 422, 503),
)
def complete_logo_upload(upload_id: UUID, user: Usuario, token: Token, service: Service) -> Profile:
    return service.complete_logo_upload(user, token, upload_id)


@router.get(
    "/api/profile/logo",
    operation_id="get_logo",
    response_model=LogoUrl,
    summary="URL firmada de 60 s para ver el logo",
    responses=problems(401, 403, 404, 503),
)
def get_logo(user: Usuario, token: Token, service: Service) -> LogoUrl:
    return service.get_logo(user, token)


@router.delete(
    "/api/profile/logo",
    operation_id="delete_logo",
    status_code=204,
    response_class=Response,
    summary="Quitar el logo y borrar su archivo (idempotente)",
    responses=problems(401, 403),
)
def delete_logo(user: Usuario, token: Token, service: Service) -> Response:
    service.delete_logo(user, token)
    return Response(status_code=204)


# --- Series -----------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/invoice-series",
    operation_id="list_invoice_series",
    response_model=list[InvoiceSeries],
    summary="Listar las series de facturación (la predeterminada primero; incluye las archivadas)",
    responses=problems(401, 403),
)
def list_invoice_series(user: Usuario, service: Service) -> list[InvoiceSeries]:
    return service.list_series(user)


@router.post(
    "/api/invoice-series",
    operation_id="create_invoice_series",
    status_code=201,
    response_model=InvoiceSeries,
    summary="Crear una serie",
    responses=problems(401, 403, 409, 422),
)
def create_invoice_series(body: SeriesCreate, user: Usuario, service: Service) -> InvoiceSeries:
    return service.create_series(user, body)


@router.patch(
    "/api/invoice-series/{series_id}",
    operation_id="update_invoice_series",
    response_model=InvoiceSeries,
    summary="Cambiar el código, la descripción o el número inicial de una serie, o archivarla y reactivarla",
    responses=problems(401, 403, 404, 409, 422),
)
def update_invoice_series(series_id: UUID, body: SeriesUpdate, user: Usuario, service: Service) -> InvoiceSeries:
    return service.update_series(user, series_id, body)


@router.put(
    "/api/invoice-series/{series_id}/default",
    operation_id="set_default_invoice_series",
    response_model=InvoiceSeries,
    summary="Hacer predeterminada una serie",
    responses=problems(401, 403, 404, 409),
)
def set_default_invoice_series(series_id: UUID, user: Usuario, service: Service) -> InvoiceSeries:
    return service.set_default_series(user, series_id)
