"""Gastos registrados (SPEC-W-003 §5.3). Solo el rol `usuario`.

Todas las rutas son cortas: no esperan a ningún servicio externo, así que cada operación abre su transacción con la identidad de la persona
(`ExpenseService`) y la cierra. `confirm_document` está en `routes_documents` (cuelga de `/api/documents/{id}`) y usa este mismo servicio.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request

from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.clock import Clock
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.expenses.models import CreateExpense, Expense, ExpensePage, SetCategory, VoidResult
from cuadre.expenses.service import LIST_DEFAULT_LIMIT, LIST_MAX_LIMIT, ExpenseService
from cuadre.validators import ExpenseCategory

router = new_router(tags=["gastos"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_expense_service(request: Request) -> ExpenseService:
    state = request.app.state
    clock: Clock = state.clock
    return ExpenseService(state.db_pool, clock)


Service = Annotated[ExpenseService, Depends(get_expense_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar gastos (solo `usuario`) o la cuenta está suspendida",
        404: "El gasto no existe (también si es de otra persona)",
        409: "El gasto está anulado o el documento no admite esa acción",
        422: "Datos no válidos, comprobaciones sin pasar o fecha fuera de rango",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


@router.post(
    "/api/expenses",
    operation_id="create_expense",
    status_code=201,
    response_model=Expense,
    summary="Anotar un gasto sin factura",
    responses=problems(401, 403, 422),
)
def create_expense(body: CreateExpense, user: Usuario, service: Service) -> Expense:
    return service.create(user, body)


@router.get(
    "/api/expenses",
    operation_id="list_expenses",
    response_model=ExpensePage,
    summary="Listar los gastos registrados (sin los anulados), del más reciente al más antiguo",
    responses=problems(401, 403, 422),
)
def list_expenses(
    user: Usuario,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=LIST_MAX_LIMIT)] = LIST_DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    category: ExpenseCategory | None = None,
) -> ExpensePage:
    return service.list(user, limit=limit, page=cursor, year=year, month=month, category=category)


@router.get(
    "/api/expenses/{expense_id}",
    operation_id="get_expense",
    response_model=Expense,
    summary="Obtener un gasto (también uno anulado)",
    responses=problems(401, 403, 404),
)
def get_expense(expense_id: UUID, user: Usuario, service: Service) -> Expense:
    return service.get(user, expense_id)


@router.put(
    "/api/expenses/{expense_id}/category",
    operation_id="set_expense_category",
    response_model=Expense,
    summary="Cambiar la categoría de un gasto no anulado",
    responses=problems(401, 403, 404, 409, 422),
)
def set_expense_category(expense_id: UUID, body: SetCategory, user: Usuario, service: Service) -> Expense:
    return service.set_category(user, expense_id, body)


@router.post(
    "/api/expenses/{expense_id}/void",
    operation_id="void_expense",
    response_model=VoidResult,
    summary="Anular un gasto: deja de contar y su documento vuelve a revisión",
    responses=problems(401, 403, 404, 409),
)
def void_expense(expense_id: UUID, user: Usuario, service: Service) -> VoidResult:
    return service.void(user, expense_id)
