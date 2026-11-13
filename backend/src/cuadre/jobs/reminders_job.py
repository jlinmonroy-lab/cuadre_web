"""Job de recordatorios del plazo trimestral (SPEC-W-014 §5.4, D-03, D-05, D-07, ADR-0007).

Para cada cuenta `usuario` activa con los avisos activados: ¿hay un plazo en su ventana? -> reservar (`reminder_claim`) -> calcular las cifras CON LA
IDENTIDAD DE ESA PERSONA (las mismas funciones que las pantallas) -> enviar -> cerrar (`reminder_mark`). La reserva va antes de enviar, así que dos
ejecuciones a la vez no duplican; un envío fallido deja la fila en `failed` y la siguiente ejecución la reclama. Un fallo con una persona no detiene
a las demás. Nada de lo que se registra lleva correo, asunto, cuerpo ni importes.
"""

import logging
import time
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.clock import today_in_madrid
from cuadre.db import service_transaction, user_transaction
from cuadre.jobs.reminders import KIND, DueQuarter, due_quarter, effective_settings, is_recipient
from cuadre.notifications import EmailDeliveryError, EmailSender, quarter_reminder
from cuadre.quarters.service import QuarterService

logger = logging.getLogger("cuadre.jobs.reminders")

Pool = ConnectionPool[Connection[DictRow]]


@dataclass(frozen=True, slots=True)
class ReminderResult:
    sent: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"sent": self.sent, "skipped": self.skipped, "failed": self.failed}


class _FixedClock:
    """El `now` de la ejecución: todo el job decide con la misma hora (y las pruebas pasan la que quieren)."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _pending_documents(conn: Connection[DictRow]) -> int:
    """Documentos por revisar de quien tiene la transacción (la RLS lo limita a lo suyo); el mismo criterio que la cartera del gestor."""
    row = conn.execute("SELECT count(*)::int AS n FROM public.documents WHERE status = 'review'").fetchone()
    assert row is not None
    return row["n"]


def _send_one(
    candidate: DictRow, due: DueQuarter, *, quarters: QuarterService, app_pool: Pool, sender: EmailSender, app_url: str
) -> None:
    """Calcula las cifras y envía. Lanza si algo falla; quien llama cierra la reserva."""
    owner: UUID = candidate["owner_id"]
    user = CurrentUser(
        id=owner,
        email=candidate["email"],
        display_name=candidate["display_name"],
        role="usuario",
        status="active",
        claims={},
    )
    modelo_303 = quarters.modelo_303(user, due.year, due.quarter)
    modelo_130 = quarters.modelo_130(user, due.year, due.quarter)
    with user_transaction(app_pool, owner) as conn:
        pending = _pending_documents(conn)
    message = quarter_reminder(
        to=candidate["email"],
        name=candidate["display_name"],
        year=due.year,
        quarter=due.quarter,
        deadline=due.deadline,
        days_left=due.days_left,
        modelo_303=(modelo_303.result_cents, modelo_303.result_kind),
        modelo_130=(modelo_130.result_cents, modelo_130.result_kind),
        pending_documents=pending,
        app_url=app_url,
    )
    sender.send(message)


def _mark(service_pool: Pool, owner: UUID, period: str, *, sent: bool) -> None:
    """Cierra la reserva. Si el cierre falla se reintenta una vez: un correo enviado y no marcado se reenviaría pasados 15 minutos."""
    for attempt in (1, 2):
        try:
            with service_transaction(service_pool) as conn:
                conn.execute("SELECT private.reminder_mark(%s, %s, %s, %s)", (owner, period, KIND, sent))
            return
        except Exception:
            logger.exception(
                "reminder_mark_failed", extra={"user_id": str(owner), "period": period, "attempt": attempt}
            )


def run_reminders(
    *,
    service_pool: Pool,
    app_pool: Pool,
    sender: EmailSender,
    now: datetime,
    app_url: str,
    only_owners: Collection[UUID] | None = None,
) -> ReminderResult:
    """Ejecuta el job con la hora `now` (con zona). `only_owners` limita a unas cuentas (operación manual y pruebas)."""
    clock = _FixedClock(now)
    today = today_in_madrid(clock)
    quarters = QuarterService(app_pool, clock)
    wanted = {UUID(str(o)) for o in only_owners} if only_owners is not None else None

    with service_transaction(service_pool) as conn:
        candidates = conn.execute("SELECT * FROM private.reminder_candidates()").fetchall()

    sent = skipped = failed = 0
    for candidate in candidates:
        owner: UUID = candidate["owner_id"]
        if wanted is not None and owner not in wanted:
            continue
        enabled, lead_days = effective_settings({"enabled": candidate["enabled"], "lead_days": candidate["lead_days"]})
        if not is_recipient(role="usuario", status="active", enabled=enabled, email=candidate["email"]):
            skipped += 1
            continue
        due = due_quarter(today, lead_days)
        if due is None:
            skipped += 1
            continue
        started = time.monotonic()
        with service_transaction(service_pool) as conn:
            row = conn.execute("SELECT private.reminder_claim(%s, %s, %s) AS ok", (owner, due.period, KIND)).fetchone()
        if row is None or not row["ok"]:
            skipped += 1
            continue
        result = "sent"
        try:
            _send_one(candidate, due, quarters=quarters, app_pool=app_pool, sender=sender, app_url=app_url)
        except EmailDeliveryError:
            result = "delivery_failed"
        except Exception as exc:  # un fallo con una persona no detiene a las demás (D-07); el tipo basta, el mensaje podría llevar datos
            result = f"error_{type(exc).__name__}"
        _mark(service_pool, owner, due.period, sent=result == "sent")
        if result == "sent":
            sent += 1
        else:
            failed += 1
        logger.info(
            "reminder_processed",
            extra={
                "user_id": str(owner),
                "period": due.period,
                "result": result,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
    return ReminderResult(sent=sent, skipped=skipped, failed=failed)
