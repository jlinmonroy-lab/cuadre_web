"""Impuestos: los borradores de los modelos 303 y 130 de un trimestre (SPEC-W-008 y SPEC-W-009, §5.3). Solo el rol `usuario`.

Es una lectura: no crea ni cambia nada (T8-07). El borrador es orientativo y nada se envía a la AEAT (RES-04). Todo lo calcula el servidor con
reglas deterministas; la interfaz solo lo enseña.
"""

from typing import Annotated

from fastapi import Depends, Query, Request, Response

from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.quarters.models import Modelo130, Modelo303
from cuadre.quarters.service import QuarterService

router = new_router(tags=["impuestos"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_quarter_service(request: Request) -> QuarterService:
    state = request.app.state
    return QuarterService(state.db_pool, state.clock)


Service = Annotated[QuarterService, Depends(get_quarter_service)]

PROBLEMS: dict[int | str, dict[str, object]] = {
    401: {"model": ProblemDetails, "description": "Sin sesión, o sesión inválida o caducada"},
    403: {
        "model": ProblemDetails,
        "description": "El rol de la cuenta no puede ver el borrador (solo `usuario`) o la cuenta está suspendida",
    },
    422: {
        "model": ProblemDetails,
        "description": (
            "Periodo que no existe (`invalid_period`), trimestre futuro (`period_in_future`), trimestre con demasiados "
            "documentos (`quarter_too_large`) o un documento con un tipo de IVA que no se puede interpretar "
            "(`unsupported_vat_rate`)"
        ),
    },
}


@router.get(
    "/api/tax/303",
    operation_id="get_modelo_303",
    response_model=Modelo303,
    summary="Borrador orientativo del modelo 303 de un trimestre, con cada casilla enlazada a sus facturas y gastos",
    responses=PROBLEMS,
)
def get_modelo_303(
    user: Usuario,
    service: Service,
    response: Response,
    year: Annotated[int | None, Query(description="Año; por defecto el actual (Europe/Madrid)")] = None,
    quarter: Annotated[
        int | None, Query(description="Trimestre (1 a 4); por defecto el actual (Europe/Madrid)")
    ] = None,
) -> Modelo303:
    response.headers["Cache-Control"] = "private, no-store"
    return service.modelo_303(user, year, quarter)


PROBLEMS_130: dict[int | str, dict[str, object]] = {
    **PROBLEMS,
    422: {
        "model": ProblemDetails,
        "description": (
            "Periodo que no existe (`invalid_period`), trimestre futuro (`period_in_future`) o periodo acumulado con "
            "demasiados documentos (`quarter_too_large`)"
        ),
    },
}


@router.get(
    "/api/tax/130",
    operation_id="get_modelo_130",
    response_model=Modelo130,
    summary="Borrador orientativo del modelo 130 de un trimestre, acumulado desde enero y con cada casilla enlazada a sus facturas y gastos",
    responses=PROBLEMS_130,
)
def get_modelo_130(
    user: Usuario,
    service: Service,
    response: Response,
    year: Annotated[int | None, Query(description="Año; por defecto el actual (Europe/Madrid)")] = None,
    quarter: Annotated[
        int | None, Query(description="Trimestre (1 a 4); por defecto el actual (Europe/Madrid)")
    ] = None,
) -> Modelo130:
    response.headers["Cache-Control"] = "private, no-store"
    return service.modelo_130(user, year, quarter)
