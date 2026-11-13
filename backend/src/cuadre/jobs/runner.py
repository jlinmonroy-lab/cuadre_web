"""Punto de entrada común de los jobs para la ruta interna y la CLI (SPEC-W-014 §5.4, SPEC-W-012 §5.4, ADR-0007 y ADR-0016).

Es el ÚNICO sitio, junto con `cuadre.cli`, que abre el pool de servicio: la ruta de la API no toca `DATABASE_SERVICE_URL` (T-04). El pool se abre y se
cierra en cada ejecución: en una función serverless no hay proceso persistente que lo conserve.

Los jobs se registran por nombre en `JOBS`; la ruta y la CLI no saben cuáles hay.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.closing.types import YearMonth
from cuadre.config import Settings
from cuadre.db import open_pool
from cuadre.jobs.closing_job import run_monthly_closing
from cuadre.jobs.reminders_job import run_reminders
from cuadre.notifications import EmailSender

Pool = ConnectionPool[Connection[DictRow]]


@dataclass(frozen=True, slots=True)
class JobContext:
    """Lo que recibe cada job. `month` solo lo usan los que trabajan por meses (`monthly_closing`)."""

    service_pool: Pool
    app_pool: Pool
    sender: EmailSender
    now: datetime
    app_url: str
    only_owners: Collection[UUID] | None
    month: YearMonth | None


def _reminders(context: JobContext) -> dict[str, int]:
    return run_reminders(
        service_pool=context.service_pool,
        app_pool=context.app_pool,
        sender=context.sender,
        now=context.now,
        app_url=context.app_url,
        only_owners=context.only_owners,
    ).as_dict()


def _monthly_closing(context: JobContext) -> dict[str, int]:
    return run_monthly_closing(
        service_pool=context.service_pool,
        app_pool=context.app_pool,
        now=context.now,
        only_owners=context.only_owners,
        month=context.month,
    ).as_dict()


JOBS: dict[str, Callable[[JobContext], dict[str, int]]] = {"reminders": _reminders, "monthly_closing": _monthly_closing}
JOB_NAMES = tuple(JOBS)
# Los jobs que admiten pedir un mes concreto.
MONTHLY_JOBS = frozenset({"monthly_closing"})


class UnknownJob(Exception):
    """No existe ningún job con ese nombre."""


class JobConfigurationError(Exception):
    """Falta algo de la configuración para ejecutar el job (por ejemplo, `DATABASE_SERVICE_URL`)."""


def run_named_job(
    name: str,
    *,
    settings: Settings,
    app_pool: Pool,
    sender: EmailSender,
    now: datetime,
    only_owners: Collection[UUID] | None = None,
    month: YearMonth | None = None,
) -> dict[str, int]:
    """Ejecuta el job `name` con la hora `now` y devuelve sus contadores. `app_pool` es el de la aplicación (rol `cuadre_app`)."""
    if name not in JOBS:
        raise UnknownJob(name)
    if now.tzinfo is None:
        raise ValueError("`now` debe llevar zona horaria.")
    if month is not None and name not in MONTHLY_JOBS:
        raise ValueError("Esta tarea no trabaja por meses.")
    if settings.database_service_url is None:
        raise JobConfigurationError("DATABASE_SERVICE_URL")
    service_pool = open_pool(settings.database_service_url, name="jobs", min_size=1, max_size=2)
    try:
        context = JobContext(
            service_pool=service_pool,
            app_pool=app_pool,
            sender=sender,
            now=now,
            app_url=settings.frontend_origin,
            only_owners=only_owners,
            month=month,
        )
        return JOBS[name](context)
    finally:
        service_pool.close()
