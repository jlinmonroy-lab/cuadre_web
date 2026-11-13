"""Job del cierre mensual (SPEC-W-012 §5.4, D-04, D-05, D-07, ADR-0007).

Para cada cuenta `usuario` activa: ¿qué meses toca cerrar? (los últimos 12 ya terminados, sin pasar de su primer mes con actividad) -> leer sus facturas y
gastos CON SU IDENTIDAD (las mismas lecturas que las pantallas) -> calcular la foto de cada mes con `cuadre.closing` -> guardarla con `private.close_month`,
que dice si cerró, reabrió o no cambió nada. El día 1 se cierra el mes que acaba de terminar; el resto de los días el recálculo detecta documentos atrasados y
reabre y vuelve a cerrar lo que cambió (`revision + 1`). Repetir es seguro. Un fallo con una persona no detiene a las demás.

Cada mes se guarda en su propia transacción de servicio: si algo falla a medias, lo ya guardado sigue valiendo y la siguiente ejecución sigue desde ahí.
Nada de lo que se registra lleva nombres de clientes, importes ni correos.
"""

import logging
import time
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from cuadre.closing import (
    YearMonth,
    build_months,
    closing_window,
    explicit_window,
    first_active_month,
    payload_of,
    window_bounds,
)
from cuadre.closing.repository import expenses_between, first_dates, invoices_between
from cuadre.core.clock import MADRID, today_in_madrid
from cuadre.db import service_transaction, user_transaction

logger = logging.getLogger("cuadre.jobs.closing")

Pool = ConnectionPool[Connection[DictRow]]


@dataclass(frozen=True, slots=True)
class ClosingResult:
    """`closed`, `reopened` y `unchanged` cuentan MESES; `failed` cuenta PERSONAS cuyo cierre falló."""

    closed: int = 0
    reopened: int = 0
    unchanged: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"closed": self.closed, "reopened": self.reopened, "unchanged": self.unchanged, "failed": self.failed}


class _FixedClock:
    """El `now` de la ejecución: todo el job decide con la misma hora (y las pruebas pasan la que quieren)."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _close_person(
    owner: UUID,
    created_at: datetime,
    *,
    service_pool: Pool,
    app_pool: Pool,
    today: date,
    requested: tuple[YearMonth, ...] | None,
) -> tuple[int, int, int]:
    """Cierra los meses de una persona y devuelve `(cerrados, reabiertos, sin cambios)`. `today` es el día de hoy en Madrid."""
    with user_transaction(app_pool, owner) as conn:
        first_invoice, first_expense = first_dates(conn)
        first = first_active_month(created_at.astimezone(MADRID).date(), first_invoice, first_expense)
        if requested is None:
            window = closing_window(today, first)
        else:
            window = tuple(
                m for m in requested if first is not None and m >= first
            )  # antes de su primer mes no hay cierres
        if not window:
            return 0, 0, 0
        start, end = window_bounds(window)
        invoices = invoices_between(conn, start, end)
        expenses = expenses_between(conn, start, end)

    closed = reopened = unchanged = 0
    for totals in build_months(invoices, expenses, window):
        with service_transaction(service_pool) as conn:
            row = conn.execute(
                "SELECT private.close_month(%s, %s, %s, %s) AS result",
                (owner, totals.year, totals.month, Jsonb(payload_of(totals))),
            ).fetchone()
        assert row is not None
        match row["result"]:
            case "closed":
                closed += 1
            case "reopened":
                reopened += 1
                logger.info(
                    "closing_reopened",
                    extra={"user_id": str(owner), "period": YearMonth(totals.year, totals.month).label},
                )
            case _:
                unchanged += 1
    return closed, reopened, unchanged


def run_monthly_closing(
    *,
    service_pool: Pool,
    app_pool: Pool,
    now: datetime,
    only_owners: Collection[UUID] | None = None,
    month: YearMonth | None = None,
) -> ClosingResult:
    """Ejecuta el cierre con la hora `now` (con zona). `only_owners` limita a unas cuentas (operación manual y pruebas); `month` recalcula un único mes,
    aunque esté fuera de la ventana de 12 meses, y se valida antes de tocar a nadie (`InvalidMonth` o `PeriodInFuture` al llamante)."""
    today = today_in_madrid(_FixedClock(now))
    requested = explicit_window(today, month.year, month.month) if month is not None else None
    wanted = {UUID(str(o)) for o in only_owners} if only_owners is not None else None

    with service_transaction(service_pool) as conn:
        candidates = conn.execute("SELECT * FROM private.closing_candidates()").fetchall()

    closed = reopened = unchanged = failed = 0
    for candidate in candidates:
        owner: UUID = candidate["owner_id"]
        if wanted is not None and owner not in wanted:
            continue
        started = time.monotonic()
        try:
            c, r, u = _close_person(
                owner,
                candidate["created_at"],
                service_pool=service_pool,
                app_pool=app_pool,
                today=today,
                requested=requested,
            )
        except (
            Exception
        ) as exc:  # un fallo con una persona no detiene a las demás; el tipo basta, el mensaje podría llevar datos
            failed += 1
            logger.warning(
                "closing_failed",
                extra={
                    "user_id": str(owner),
                    "error": type(exc).__name__,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                },
            )
            continue
        closed, reopened, unchanged = closed + c, reopened + r, unchanged + u
        if c or r or u:
            logger.info(
                "closing_processed",
                extra={
                    "user_id": str(owner),
                    "months": c + r + u,
                    "closed": c,
                    "reopened": r,
                    "unchanged": u,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                },
            )
    return ClosingResult(closed=closed, reopened=reopened, unchanged=unchanged, failed=failed)
