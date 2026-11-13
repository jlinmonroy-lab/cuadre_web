"""Rutas internas del planificador (SPEC-W-014 §5.3, D-06, ADR-0007 y ADR-0016). No son API pública: no salen en `openapi.json` ni en el cliente generado.

El planificador de la plataforma hace un GET con `Authorization: Bearer <CRON_SECRET>`. Sin `CRON_SECRET` configurado la ruta responde siempre 401: nunca
queda abierta por olvido. No se registra el secreto ni se explica por qué se rechaza.
"""

import hmac

from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool

from cuadre.core.errors import ProblemError, unauthenticated
from cuadre.core.routing import new_router
from cuadre.jobs.runner import JobConfigurationError, UnknownJob, run_named_job

router = new_router(tags=["interno"])

_PREFIX = "bearer "


def require_cron_secret(request: Request) -> None:
    secret = request.app.state.settings.cron_secret
    header = request.headers.get("authorization", "")
    if secret is None or not header.lower().startswith(_PREFIX):
        raise unauthenticated()
    given = header[len(_PREFIX) :].strip().encode()
    if not hmac.compare_digest(given, secret.get_secret_value().encode()):
        raise unauthenticated()


@router.get(
    "/internal/jobs/{name}",
    operation_id="run_job",
    include_in_schema=False,
    dependencies=[Depends(require_cron_secret)],
)
async def run_job(name: str, request: Request) -> dict[str, int]:
    state = request.app.state
    try:
        return await run_in_threadpool(
            run_named_job,
            name,
            settings=state.settings,
            app_pool=state.db_pool,
            sender=state.email_sender,
            now=state.clock.now(),
        )
    except UnknownJob:
        raise ProblemError(
            404, "job_not_found", "Tarea desconocida", "No existe ninguna tarea con ese nombre."
        ) from None
    except JobConfigurationError:
        raise ProblemError(
            503, "job_unavailable", "Tarea no disponible", "La tarea no está configurada en este entorno."
        ) from None
