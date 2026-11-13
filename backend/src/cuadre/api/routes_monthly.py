"""Contabilidad mensual: los meses cerrados del año y el detalle de uno (SPEC-W-012 §5.3). Solo el rol `usuario`.

Son lecturas: no escriben nada. Los cierres los hace el job (`cuadre.jobs.closing_job`); aquí solo se enseñan, y el mes en curso y los terminados aún sin
cierre se calculan en vivo con las mismas reglas.
"""

from typing import Annotated

from fastapi import Depends, Query, Request, Response

from cuadre.closing.models import MonthlyClosing, MonthlyClosings
from cuadre.closing.service import MonthlyClosingService
from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router

router = new_router(tags=["contabilidad mensual"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_monthly_service(request: Request) -> MonthlyClosingService:
    state = request.app.state
    return MonthlyClosingService(state.db_pool, state.clock)


Service = Annotated[MonthlyClosingService, Depends(get_monthly_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede ver la contabilidad mensual (solo `usuario`) o la cuenta está suspendida",
        404: "Ese mes no se muestra: la cuenta todavía no tenía actividad (`closing_not_found`)",
        422: "Año o mes que no existen (`invalid_period`) o que todavía no han empezado (`period_in_future`)",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get(
    "/api/monthly-closings",
    operation_id="get_monthly_closings",
    response_model=MonthlyClosings,
    summary="Los meses del año con sus totales por ámbito, el acumulado y el estado del cierre",
    responses=problems(401, 403, 422),
)
def get_monthly_closings(
    user: Usuario,
    service: Service,
    response: Response,
    year: Annotated[int | None, Query(description="Año a consultar; por defecto, el de hoy en Europe/Madrid")] = None,
) -> MonthlyClosings:
    no_store(response)
    return service.year(user, year)


@router.get(
    "/api/monthly-closings/{year}/{month}",
    operation_id="get_monthly_closing",
    response_model=MonthlyClosing,
    summary="Un mes con sus ingresos por cliente y ámbito",
    responses=problems(401, 403, 404, 422),
)
def get_monthly_closing(year: int, month: int, user: Usuario, service: Service, response: Response) -> MonthlyClosing:
    no_store(response)
    return service.month(user, year, month)
