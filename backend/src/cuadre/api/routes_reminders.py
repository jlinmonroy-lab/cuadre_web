"""Ajustes de los recordatorios por correo (SPEC-W-014 §5.3). Solo el rol `usuario`.

Es lo único que la persona controla del job de recordatorios: si los quiere y con cuántos días de antelación. Nada de esto envía nada.
"""

from typing import Annotated

from fastapi import Depends, Request, Response

from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.errors import ProblemDetails
from cuadre.core.routing import new_router
from cuadre.reminders import ReminderSettings, ReminderSettingsInput, ReminderSettingsService

router = new_router(tags=["recordatorios"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_reminder_service(request: Request) -> ReminderSettingsService:
    return ReminderSettingsService(request.app.state.db_pool)


Service = Annotated[ReminderSettingsService, Depends(get_reminder_service)]


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar los recordatorios (solo `usuario`) o la cuenta está suspendida",
        422: "Antelación fuera de 1 a 30 días (`invalid_lead_days`) o cuerpo con la forma incorrecta",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get(
    "/api/me/reminders",
    operation_id="get_reminder_settings",
    response_model=ReminderSettings,
    summary="Leer los ajustes de recordatorios (sin ajustes guardados: activados y 10 días)",
    responses=problems(401, 403),
)
def get_reminder_settings(user: Usuario, service: Service, response: Response) -> ReminderSettings:
    no_store(response)
    return service.get(user)


@router.put(
    "/api/me/reminders",
    operation_id="update_reminder_settings",
    response_model=ReminderSettings,
    summary="Guardar los ajustes de recordatorios (activar o no, y de 1 a 30 días de antelación)",
    responses=problems(401, 403, 422),
)
def update_reminder_settings(
    body: ReminderSettingsInput, user: Usuario, service: Service, response: Response
) -> ReminderSettings:
    no_store(response)
    return service.put(user, body)
