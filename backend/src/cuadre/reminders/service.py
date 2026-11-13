"""Leer y guardar los ajustes de recordatorios de la persona (SPEC-W-014 §5.3, D-01).

Sin fila en `reminder_settings` valen los de por defecto (activado y 10 días). El rango lo comprueba `cuadre.jobs.reminders.check_lead_days`
(la misma regla que usa el job) y, de nuevo, la función SQL. La tabla solo se escribe por `app.set_reminder_settings`.
"""

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction
from cuadre.jobs.reminders import DEFAULT_ENABLED, DEFAULT_LEAD_DAYS, check_lead_days
from cuadre.reminders.models import ReminderSettings, ReminderSettingsInput


def invalid_lead_days() -> ProblemError:
    return ProblemError(
        422,
        "invalid_lead_days",
        "Antelación no válida",
        "La antelación debe ser un número entero de días entre 1 y 30.",
        extra={"field": "lead_days"},
    )


def _read(conn: Connection[DictRow]) -> ReminderSettings:
    # La RLS limita la lectura a la fila de quien tiene la transacción.
    row = conn.execute("SELECT enabled, lead_days FROM public.reminder_settings").fetchone()
    if row is None:
        return ReminderSettings(enabled=DEFAULT_ENABLED, lead_days=DEFAULT_LEAD_DAYS)
    return ReminderSettings(enabled=row["enabled"], lead_days=row["lead_days"])


class ReminderSettingsService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]]) -> None:
        self.pool = pool

    def get(self, user: CurrentUser) -> ReminderSettings:
        with user_transaction(self.pool, user.id, user.claims) as conn:
            return _read(conn)

    def put(self, user: CurrentUser, body: ReminderSettingsInput) -> ReminderSettings:
        try:
            check_lead_days(body.lead_days)
        except ValueError:
            raise invalid_lead_days() from None
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                conn.execute("SELECT app.set_reminder_settings(%s, %s)", (body.enabled, body.lead_days))
                return _read(conn)
        except psycopg.errors.RaiseException as exc:  # P0001: la función SQL tiene la última palabra
            if str(exc).splitlines()[0] == "invalid_lead_days":
                raise invalid_lead_days() from None
            raise
