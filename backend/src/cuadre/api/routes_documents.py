"""Subida, lectura y revisión de facturas de compra (SPEC-W-002 §5.1). Solo el rol `usuario`.

Rutas síncronas: `complete` y `retry` esperan al agente hasta 45 s DENTRO de la petición (D-02; en Vercel no hay trabajo posterior a la
respuesta). Por eso usan `require_role_detached`: la conexión de base de datos no se retiene mientras se espera (cada paso abre su
transacción corta en `DocumentService`). Ningún archivo pasa por la API: la persona sube a Storage con una URL firmada (T2-14).
"""

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from starlette.responses import Response

from cuadre.agents import AgentsClient
from cuadre.api.routes_expenses import ExpenseService, get_expense_service
from cuadre.core.auth import CurrentUser, get_verified_token, require_role_detached
from cuadre.core.clock import Clock
from cuadre.core.errors import ProblemDetails, request_id_of
from cuadre.core.routing import new_router
from cuadre.documents.models import (
    Document,
    DocumentState,
    DocumentSummary,
    PreviewResponse,
    Review,
    UploadRequest,
    UploadResponse,
)
from cuadre.documents.service import DocumentService
from cuadre.documents.storage import StorageGateway
from cuadre.expenses.models import ConfirmRequest, Expense

router = new_router(tags=["documentos"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]
Token = Annotated[str, Depends(get_verified_token)]


def get_service(request: Request) -> DocumentService:
    state = request.app.state
    storage: StorageGateway = state.storage
    agents: AgentsClient = state.agents_client
    clock: Clock = state.clock
    return DocumentService(state.db_pool, storage, agents, clock)


Service = Annotated[DocumentService, Depends(get_service)]
Expenses = Annotated[ExpenseService, Depends(get_expense_service)]


def request_id(request: Request) -> str:
    """El identificador de la petición (ya validado por el middleware) viaja al agente como `X-Request-Id`."""
    return request_id_of(request) or uuid.uuid4().hex


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida",
        404: "El documento no existe (también si es de otra persona)",
        409: "El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura",
        413: "El archivo supera el máximo de 15 MB",
        415: "Tipo de archivo no admitido",
        422: "Datos no válidos, archivo que no es del tipo indicado o comprobaciones sin pasar",
        429: "Demasiadas lecturas en curso (con `Retry-After`)",
        503: "Almacenamiento no disponible",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


@router.post(
    "/api/documents",
    operation_id="upload_document",
    status_code=201,
    response_model=UploadResponse,
    summary="Reservar un documento y obtener la URL firmada para subir el archivo",
    responses=problems(401, 403, 413, 415, 422, 429, 503),
)
def upload_document(body: UploadRequest, user: Usuario, token: Token, service: Service) -> UploadResponse:
    return service.create_upload(user, token, body)


@router.post(
    "/api/documents/{document_id}/complete",
    operation_id="complete_document_upload",
    response_model=DocumentState,
    summary="Comprobar el archivo subido y leerlo (espera al agente)",
    responses=problems(401, 403, 404, 409, 422, 429, 503),
)
def complete_document_upload(
    document_id: UUID, request: Request, user: Usuario, token: Token, service: Service
) -> DocumentState:
    return service.complete(user, token, document_id, request_id(request))


@router.get(
    "/api/documents",
    operation_id="list_documents",
    response_model=list[DocumentSummary],
    summary="Listar los documentos de la persona",
    responses=problems(401, 403),
)
def list_documents(user: Usuario, service: Service) -> list[DocumentSummary]:
    return service.list_documents(user)


@router.get(
    "/api/documents/{document_id}",
    operation_id="get_document",
    response_model=Document,
    summary="Obtener un documento con su lectura y sus correcciones",
    responses=problems(401, 403, 404),
)
def get_document(document_id: UUID, user: Usuario, service: Service) -> Document:
    return service.get_document(user, document_id)


@router.get(
    "/api/documents/{document_id}/preview",
    operation_id="get_document_preview",
    response_model=PreviewResponse,
    summary="URL firmada de 60 s para ver el original",
    responses=problems(401, 403, 404, 409, 503),
)
def get_document_preview(document_id: UUID, user: Usuario, token: Token, service: Service) -> PreviewResponse:
    return service.preview(user, token, document_id)


@router.put(
    "/api/documents/{document_id}/review",
    operation_id="save_document_review",
    response_model=Document,
    summary="Guardar las correcciones de la persona (la lectura original no cambia)",
    responses=problems(401, 403, 404, 409, 422),
)
def save_document_review(document_id: UUID, body: Review, user: Usuario, service: Service) -> Document:
    return service.save_review(user, document_id, body)


@router.post(
    "/api/documents/{document_id}/retry",
    operation_id="retry_document_extraction",
    response_model=DocumentState,
    summary="Volver a leer un documento que falló (espera al agente)",
    responses=problems(401, 403, 404, 409, 429, 503),
)
def retry_document_extraction(
    document_id: UUID, request: Request, user: Usuario, token: Token, service: Service
) -> DocumentState:
    return service.retry(user, token, document_id, request_id(request))


@router.delete(
    "/api/documents/{document_id}",
    operation_id="discard_document",
    status_code=204,
    response_class=Response,
    summary="Descartar un documento y borrar su archivo",
    responses=problems(401, 403, 404, 409),
)
def discard_document(document_id: UUID, user: Usuario, token: Token, service: Service) -> Response:
    service.discard(user, token, document_id)
    return Response(status_code=204)


@router.post(
    "/api/documents/{document_id}/confirm",
    operation_id="confirm_document",
    status_code=201,
    response_model=Expense,
    summary="Registrar el gasto de un documento si todas las comprobaciones pasan",
    responses=problems(401, 403, 404, 409, 422),
)
def confirm_document(document_id: UUID, body: ConfirmRequest, user: Usuario, expenses: Expenses) -> Expense:
    return expenses.confirm(user, document_id, body)
