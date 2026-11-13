"""Punto de entrada común de los jobs para la ruta interna y la CLI (SPEC-W-014 §5.4, ADR-0007 y ADR-0016).

Es el ÚNICO sitio, junto con `cuadre.cli`, que abre el pool de servicio: la ruta de la API no toca `DATABASE_SERVICE_URL` (T-04). El pool se abre y se
cierra en cada ejecución: en una función serverless no hay proceso persistente que lo conserve.
"""

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.config import Settings
from cuadre.db import open_pool
from cuadre.jobs.reminders_job import run_reminders
from cuadre.notifications import EmailSender

JOB_NAMES = ("reminders",)


class UnknownJob(Exception):
    """No existe ningún job con ese nombre."""


class JobConfigurationError(Exception):
    """Falta algo de la configuración para ejecutar el job (por ejemplo, `DATABASE_SERVICE_URL`)."""


def run_named_job(
    name: str,
    *,
    settings: Settings,
    app_pool: ConnectionPool[Connection[DictRow]],
    sender: EmailSender,
    now: datetime,
    only_owners: Collection[UUID] | None = None,
) -> dict[str, int]:
    """Ejecuta el job `name` con la hora `now` y devuelve sus contadores. `app_pool` es el de la aplicación (rol `cuadre_app`)."""
    if name not in JOB_NAMES:
        raise UnknownJob(name)
    if now.tzinfo is None:
        raise ValueError("`now` debe llevar zona horaria.")
    if settings.database_service_url is None:
        raise JobConfigurationError("DATABASE_SERVICE_URL")
    service_pool = open_pool(settings.database_service_url, name="jobs", min_size=1, max_size=2)
    try:
        return run_reminders(
            service_pool=service_pool,
            app_pool=app_pool,
            sender=sender,
            now=now,
            app_url=settings.frontend_origin,
            only_owners=only_owners,
        ).as_dict()
    finally:
        service_pool.close()
