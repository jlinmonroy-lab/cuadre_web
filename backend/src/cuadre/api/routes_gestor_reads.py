"""Lecturas del gestor por autónomo, cartera, anotaciones y registro de actividad (SPEC-W-010 §5.3). Solo lectura (CONF-001 a): lo único que escribe un gestor es una
anotación.

Cada ruta `/api/gestor/autonomos/{owner_id}/…` pasa por `cuadre.gestor.scope`: rol `gestor` (si no, `403`), vínculo activo comprobado y la lectura registrada en la
misma transacción, con un `404` uniforme si no hay vínculo (nunca se averigua qué ids son autónomos). `Cache-Control: private, no-store` en todas.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request, Response

from cuadre.clients.models import Client
from cuadre.core.auth import CurrentUser, get_verified_token, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.documents.models import DocumentSummary
from cuadre.expenses.models import ExpenseCategory
from cuadre.gestor.models import (
    ActivityPage,
    AutonomoSummary,
    ExpenseListPage,
    GestorNote,
    NoteInput,
    PortfolioEntry,
    ProfileView,
    SignedUrl,
)
from cuadre.gestor.reads import EXPENSE_LIST_DEFAULT, EXPENSE_LIST_MAX, GestorReadService
from cuadre.invoicing.models import Invoice
from cuadre.invoicing.service import InvoiceService
from cuadre.profile.service import ProfileService
from cuadre.quarters.models import Modelo130, Modelo303
from cuadre.quarters.service import QuarterService

router = new_router(tags=["gestor"])

Gestor = Annotated[CurrentUser, Depends(require_role_detached("gestor"))]
Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]
Token = Annotated[str, Depends(get_verified_token)]
Owner = Annotated[UUID, "Identificador del autónomo"]


def get_reads(request: Request) -> GestorReadService:
    state = request.app.state
    invoices = InvoiceService(state.db_pool, state.clock, state.invoice_storage, state.logo_storage)
    profile = ProfileService(state.db_pool, state.logo_storage, state.clock)
    quarters = QuarterService(state.db_pool, state.clock)
    return GestorReadService(state.db_pool, invoices, profile, quarters, state.storage, state.invoice_storage)


Reads = Annotated[GestorReadService, Depends(get_reads)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida",
        404: "No existe o no tienes acceso (sin vínculo, revocado o de otro gestor: la respuesta es siempre la misma)",
        409: "El recurso no está disponible (por ejemplo, la factura aún no tiene PDF)",
        422: "Parámetros o datos no válidos",
        503: "El almacenamiento de archivos no está disponible",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


Year = Annotated[int | None, Query(ge=2000, le=9998, description="Año; por defecto el actual (Europe/Madrid)")]
QuarterNo = Annotated[int | None, Query(description="Trimestre (1 a 4); por defecto el actual (Europe/Madrid)")]


# --- Cartera ----------------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/cartera",
    operation_id="get_gestor_portfolio",
    response_model=list[PortfolioEntry],
    summary="Los autónomos con acceso activo y sus pendientes (documentos para revisar); los de pendientes, primero",
    responses=problems(401, 403),
)
def get_gestor_portfolio(user: Gestor, reads: Reads, response: Response) -> list[PortfolioEntry]:
    no_store(response)
    return reads.portfolio(user)


@router.get(
    "/api/gestor/autonomos/{owner_id}",
    operation_id="get_gestor_autonomo",
    response_model=AutonomoSummary,
    summary="La ficha de un autónomo de la cartera: nombre, correo y pendientes",
    responses=problems(401, 403, 404),
)
def get_gestor_autonomo(owner_id: UUID, user: Gestor, reads: Reads, response: Response) -> AutonomoSummary:
    no_store(response)
    return reads.autonomo(user, owner_id)


# --- Facturas ---------------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/autonomos/{owner_id}/facturas",
    operation_id="list_gestor_autonomo_invoices",
    response_model=list[Invoice],
    summary="Las facturas de un año de un autónomo, la más reciente primero y por páginas",
    responses=problems(401, 403, 404, 422),
)
def list_gestor_autonomo_invoices(
    owner_id: UUID,
    user: Gestor,
    reads: Reads,
    response: Response,
    year: Year = None,
    scope: Annotated[Literal["national", "eu", "non_eu"] | None, Query(description="Ámbito del cliente")] = None,
    paid: Annotated[bool | None, Query(description="Solo ordinarias cobradas o pendientes de cobro")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Facturas por página")] = 100,
    offset: Annotated[int, Query(ge=0, le=100_000, description="Facturas que se saltan")] = 0,
) -> list[Invoice]:
    no_store(response)
    return reads.invoices_list(user, owner_id, year, scope, paid, limit, offset)


@router.get(
    "/api/gestor/autonomos/{owner_id}/facturas/{invoice_id}",
    operation_id="get_gestor_autonomo_invoice",
    response_model=Invoice,
    summary="Una factura de un autónomo, con las rectificativas que la corrigen y lo vigente",
    responses=problems(401, 403, 404),
)
def get_gestor_autonomo_invoice(
    owner_id: UUID, invoice_id: UUID, user: Gestor, reads: Reads, response: Response
) -> Invoice:
    no_store(response)
    return reads.invoice(user, owner_id, invoice_id)


@router.get(
    "/api/gestor/autonomos/{owner_id}/facturas/{invoice_id}/pdf",
    operation_id="get_gestor_autonomo_invoice_pdf",
    response_model=SignedUrl,
    summary="La URL firmada (≈ 60 s) del PDF de una factura de un autónomo; el archivo no pasa por la API",
    responses=problems(401, 403, 404, 409, 503),
)
def get_gestor_autonomo_invoice_pdf(
    owner_id: UUID, invoice_id: UUID, user: Gestor, token: Token, reads: Reads, response: Response
) -> SignedUrl:
    no_store(response)
    return reads.invoice_pdf(user, owner_id, invoice_id, token)


# --- Gastos y documentos ----------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/autonomos/{owner_id}/gastos",
    operation_id="list_gestor_autonomo_expenses",
    response_model=ExpenseListPage,
    summary="Los gastos de un autónomo por páginas, del más reciente al más antiguo; los anulados llevan `voided_at`",
    responses=problems(401, 403, 404, 422),
)
def list_gestor_autonomo_expenses(
    owner_id: UUID,
    user: Gestor,
    reads: Reads,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=EXPENSE_LIST_MAX)] = EXPENSE_LIST_DEFAULT,
    page: Annotated[str | None, Query(description="Cursor opaco de la página siguiente")] = None,
    year: Year = None,
    month: Annotated[int | None, Query(ge=1, le=12, description="Mes (necesita `year`)")] = None,
    category: ExpenseCategory | None = None,
) -> ExpenseListPage:
    no_store(response)
    return reads.expenses(user, owner_id, limit=limit, page=page, year=year, month=month, category=category)


@router.get(
    "/api/gestor/autonomos/{owner_id}/documentos",
    operation_id="list_gestor_autonomo_documents",
    response_model=list[DocumentSummary],
    summary="Los documentos de un autónomo pendientes de revisar o que no se pudieron leer",
    responses=problems(401, 403, 404),
)
def list_gestor_autonomo_documents(
    owner_id: UUID, user: Gestor, reads: Reads, response: Response
) -> list[DocumentSummary]:
    no_store(response)
    return reads.documents(user, owner_id)


@router.get(
    "/api/gestor/autonomos/{owner_id}/documentos/{document_id}/original",
    operation_id="get_gestor_autonomo_document_original",
    response_model=SignedUrl,
    summary="La URL firmada (≈ 60 s) del original de un documento de un autónomo; el archivo no pasa por la API",
    responses=problems(401, 403, 404, 409, 503),
)
def get_gestor_autonomo_document_original(
    owner_id: UUID, document_id: UUID, user: Gestor, token: Token, reads: Reads, response: Response
) -> SignedUrl:
    no_store(response)
    return reads.document_original(user, owner_id, document_id, token)


# --- Perfil y clientes ------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/autonomos/{owner_id}/perfil",
    operation_id="get_gestor_autonomo_profile",
    response_model=ProfileView,
    summary="El perfil del negocio de un autónomo (con su IBAN) y sus series de facturación",
    responses=problems(401, 403, 404),
)
def get_gestor_autonomo_profile(owner_id: UUID, user: Gestor, reads: Reads, response: Response) -> ProfileView:
    no_store(response)
    return reads.profile_view(user, owner_id)


@router.get(
    "/api/gestor/autonomos/{owner_id}/clientes",
    operation_id="list_gestor_autonomo_clients",
    response_model=list[Client],
    summary="Los clientes de un autónomo, también los archivados",
    responses=problems(401, 403, 404),
)
def list_gestor_autonomo_clients(owner_id: UUID, user: Gestor, reads: Reads, response: Response) -> list[Client]:
    no_store(response)
    return reads.clients(user, owner_id)


# --- Borradores 303 y 130 ---------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/autonomos/{owner_id}/trimestres/303",
    operation_id="get_gestor_autonomo_modelo_303",
    response_model=Modelo303,
    summary="El borrador orientativo del 303 de un autónomo: el mismo cuerpo que ve él",
    responses=problems(401, 403, 404, 422),
)
def get_gestor_autonomo_modelo_303(
    owner_id: UUID, user: Gestor, reads: Reads, response: Response, year: Year = None, quarter: QuarterNo = None
) -> Modelo303:
    no_store(response)
    return reads.modelo_303(user, owner_id, year, quarter)


@router.get(
    "/api/gestor/autonomos/{owner_id}/trimestres/130",
    operation_id="get_gestor_autonomo_modelo_130",
    response_model=Modelo130,
    summary="El borrador orientativo del 130 de un autónomo, acumulado desde enero: el mismo cuerpo que ve él",
    responses=problems(401, 403, 404, 422),
)
def get_gestor_autonomo_modelo_130(
    owner_id: UUID, user: Gestor, reads: Reads, response: Response, year: Year = None, quarter: QuarterNo = None
) -> Modelo130:
    no_store(response)
    return reads.modelo_130(user, owner_id, year, quarter)


# --- Anotaciones ------------------------------------------------------------------------------------------------------------------


@router.post(
    "/api/gestor/autonomos/{owner_id}/anotaciones",
    operation_id="create_gestor_note",
    status_code=201,
    response_model=GestorNote,
    summary="Dejar una anotación sobre un autónomo (solo se añaden; el autónomo la ve)",
    responses=problems(401, 403, 404, 422),
)
def create_gestor_note(owner_id: UUID, body: NoteInput, user: Gestor, reads: Reads, response: Response) -> GestorNote:
    no_store(response)
    return reads.create_note(user, owner_id, body)


@router.get(
    "/api/gestor/autonomos/{owner_id}/anotaciones",
    operation_id="list_gestor_autonomo_notes",
    response_model=list[GestorNote],
    summary="Las anotaciones que este gestor ha dejado sobre un autónomo",
    responses=problems(401, 403, 404),
)
def list_gestor_autonomo_notes(owner_id: UUID, user: Gestor, reads: Reads, response: Response) -> list[GestorNote]:
    no_store(response)
    return reads.notes_of(user, owner_id)


# --- Del autónomo -----------------------------------------------------------------------------------------------------------------


@router.get(
    "/api/gestor/anotaciones",
    operation_id="list_gestor_notes",
    response_model=list[GestorNote],
    summary="Las anotaciones que su gestor le ha dejado, la más reciente primero",
    responses=problems(401, 403),
)
def list_gestor_notes(user: Usuario, reads: Reads, response: Response) -> list[GestorNote]:
    no_store(response)
    return reads.my_notes(user)


@router.get(
    "/api/gestor/actividad",
    operation_id="list_gestor_activity",
    response_model=ActivityPage,
    summary="Qué se ha hecho con el acceso de su gestor (invitar, aceptar, revocar y cada lectura), la más reciente primero y por cursor",
    responses=problems(401, 403, 422),
)
def list_gestor_activity(
    user: Usuario,
    reads: Reads,
    response: Response,
    cursor: Annotated[str | None, Query(description="`next_cursor` de la página anterior")] = None,
) -> ActivityPage:
    no_store(response)
    return reads.my_activity(user, cursor)
