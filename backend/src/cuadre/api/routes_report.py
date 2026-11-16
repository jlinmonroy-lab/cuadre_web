"""Reporte mensual visual: las cifras de un mes con su comparación, su tendencia y sus gastos por categoría (SPEC-W-013 §5.3). Solo el rol `usuario`.

Es una lectura: no escribe nada. Las cifras salen de la misma foto que la contabilidad mensual; ningún importe «a apartar» (D-08).
"""

from typing import Annotated

from fastapi import Depends, Request, Response

from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.reports.models import MonthlyReport
from cuadre.reports.service import MonthlyReportService

router = new_router(tags=["reporte mensual"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_report_service(request: Request) -> MonthlyReportService:
    state = request.app.state
    return MonthlyReportService(state.db_pool, state.clock)


Service = Annotated[MonthlyReportService, Depends(get_report_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede ver el reporte mensual (solo `usuario`) o la cuenta está suspendida",
        404: "Ese mes no se muestra: la cuenta todavía no tenía actividad (`closing_not_found`)",
        422: "Año o mes que no existen (`invalid_period`), que todavía no han empezado (`period_in_future`) o con demasiados gastos (`report_too_large`)",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


@router.get(
    "/api/monthly-report/{year}/{month}",
    operation_id="get_monthly_report",
    response_model=MonthlyReport,
    summary="El reporte de un mes: ingresos por ámbito y cliente, gastos por categoría, comparación con el mes anterior y tendencia",
    responses=problems(401, 403, 404, 422),
)
def get_monthly_report(year: int, month: int, user: Usuario, service: Service, response: Response) -> MonthlyReport:
    response.headers["Cache-Control"] = "private, no-store"
    return service.report(user, year, month)
