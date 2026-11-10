"""Facturas: vista previa, emitir, rectificar, cobrar, listar y lo facturado por cliente (SPEC-W-007 §5.3). Solo el rol `usuario`.

Una factura emitida no se edita ni se borra (RES-03, T7-02): la API no ofrece `PUT` ni `DELETE` de facturas, solo cobrarlas y rectificarlas. Las
condiciones fiscales, los importes y la mención los calcula el servidor; la persona escribe el cliente, la fecha, el concepto y la base. El PDF es del
hito 4: aquí `pdf_status` dice si ya existe.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request

from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.invoicing.models import (
    ClientBilling,
    Invoice,
    InvoiceInput,
    InvoicePreview,
    PaymentInput,
    RectificationInput,
)
from cuadre.invoicing.service import InvoiceService

router = new_router(tags=["facturas"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]
Year = Annotated[
    int | None, Query(ge=2000, le=9998, description="Año de expedición; por defecto el actual (Europe/Madrid)")
]


def get_invoice_service(request: Request) -> InvoiceService:
    state = request.app.state
    return InvoiceService(state.db_pool, state.clock)


Service = Annotated[InvoiceService, Depends(get_invoice_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida",
        404: "La factura no existe (también si es de otra persona)",
        409: (
            "No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie "
            "(`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, "
            "serie agotada o factura cambiada mientras se rectificaba"
        ),
        422: (
            "Datos no válidos (`invalid_invoice` con `fields`), perfil incompleto (`profile_incomplete` con `missing`) o retención sin elegir "
            "(`irpf_rate_missing`)"
        ),
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


@router.post(
    "/api/invoices/preview",
    operation_id="preview_invoice",
    response_model=InvoicePreview,
    summary="Vista previa de una factura: ámbito, importes y mención, sin número y sin escribir nada",
    responses=problems(401, 403, 409, 422),
)
def preview_invoice(body: InvoiceInput, user: Usuario, service: Service) -> InvoicePreview:
    return service.preview(user, body)


@router.post(
    "/api/invoices",
    operation_id="issue_invoice",
    status_code=201,
    response_model=Invoice,
    summary="Emitir una factura (todo o nada, con todos los errores a la vez)",
    responses=problems(401, 403, 409, 422),
)
def issue_invoice(body: InvoiceInput, user: Usuario, service: Service) -> Invoice:
    return service.issue_invoice(user, body)


@router.post(
    "/api/invoices/{invoice_id}/rectifications",
    operation_id="issue_rectifying_invoice",
    status_code=201,
    response_model=Invoice,
    summary="Emitir una rectificativa por diferencias de la factura indicada",
    responses=problems(401, 403, 404, 409, 422),
)
def issue_rectifying_invoice(invoice_id: UUID, body: RectificationInput, user: Usuario, service: Service) -> Invoice:
    return service.issue_rectification(user, invoice_id, body)


@router.get(
    "/api/invoices",
    operation_id="list_invoices",
    response_model=list[Invoice],
    summary="Listar las facturas de un año, la más reciente primero",
    responses=problems(401, 403, 422),
)
def list_invoices(
    user: Usuario,
    service: Service,
    year: Year = None,
    scope: Annotated[Literal["national", "eu", "non_eu"] | None, Query(description="Ámbito del cliente")] = None,
    paid: Annotated[bool | None, Query(description="Solo ordinarias cobradas o pendientes de cobro")] = None,
) -> list[Invoice]:
    return service.list_invoices(user, year, scope, paid)


@router.get(
    "/api/invoices/{invoice_id}",
    operation_id="get_invoice",
    response_model=Invoice,
    summary="Obtener una factura, con las rectificativas que la corrigen y lo vigente",
    responses=problems(401, 403, 404),
)
def get_invoice(invoice_id: UUID, user: Usuario, service: Service) -> Invoice:
    return service.get_invoice(user, invoice_id)


@router.put(
    "/api/invoices/{invoice_id}/payment",
    operation_id="set_invoice_payment",
    response_model=Invoice,
    summary="Marcar una factura ordinaria como cobrada o pendiente (lo único que cambia en una factura)",
    responses=problems(401, 403, 404, 409),
)
def set_invoice_payment(invoice_id: UUID, body: PaymentInput, user: Usuario, service: Service) -> Invoice:
    return service.set_payment(user, invoice_id, body.paid)


@router.get(
    "/api/clients/billing",
    operation_id="get_clients_billing",
    response_model=list[ClientBilling],
    summary="Lo facturado a cada cliente en un año (suma de bases con signo)",
    responses=problems(401, 403, 422),
)
def get_clients_billing(user: Usuario, service: Service, year: Year = None) -> list[ClientBilling]:
    return service.billing(user, year)
