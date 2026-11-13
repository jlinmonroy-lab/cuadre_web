"""La contabilidad mensual que ve la persona (SPEC-W-012 §5.3, D-02, D-03, D-08). Una lectura: no escribe nada.

Lista y detalle comparten un único cálculo del año. Los meses con cierre devuelven su FOTO guardada (con su `revision`); el mes en curso y los terminados
que aún no tienen cierre se calculan en vivo con las mismas reglas puras que usa el job. El acumulado del año se suma aquí y nunca se guarda. Una foto no
se refresca al leer: un documento atrasado se verá en el siguiente cierre del job (por eso existe `revision`).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.closing import errors
from cuadre.closing.limits import FIRST_YEAR, LAST_YEAR
from cuadre.closing.models import ClientTotalsOut, MonthlyClosing, MonthlyClosings, MonthRow, YearTotals
from cuadre.closing.repository import expenses_between, first_dates, invoices_between
from cuadre.closing.rules import build_months, first_active_month, window_bounds
from cuadre.closing.types import MonthTotals, YearMonth
from cuadre.core.auth import CurrentUser
from cuadre.core.clock import MADRID, Clock, today_in_madrid
from cuadre.db import user_transaction

CREATED_SQL = "SELECT created_at FROM public.profiles WHERE id = (SELECT private.read_owner())"
STORED_SQL = """
SELECT month, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, expenses_cents, by_client, revision, closed_at
  FROM public.monthly_closings
 WHERE owner_id = (SELECT private.read_owner()) AND year = %(year)s
 ORDER BY month
"""


@dataclass(frozen=True, slots=True)
class _Month:
    month: int
    status: str
    invoice_count: int
    national_cents: int
    eu_cents: int
    non_eu_cents: int
    total_cents: int
    expenses_cents: int
    revision: int | None
    closed_at: datetime | None
    by_client: list[ClientTotalsOut] = field(default_factory=list)


def _from_stored(row: dict[str, Any]) -> _Month:
    return _Month(
        month=row["month"],
        status="closed",
        invoice_count=row["invoice_count"],
        national_cents=row["national_cents"],
        eu_cents=row["eu_cents"],
        non_eu_cents=row["non_eu_cents"],
        total_cents=row["total_cents"],
        expenses_cents=row["expenses_cents"],
        revision=row["revision"],
        closed_at=row["closed_at"],
        by_client=[ClientTotalsOut(**client) for client in row["by_client"]],
    )


def _from_live(totals: MonthTotals, status: str) -> _Month:
    return _Month(
        month=totals.month,
        status=status,
        invoice_count=totals.invoice_count,
        national_cents=totals.national_cents,
        eu_cents=totals.eu_cents,
        non_eu_cents=totals.non_eu_cents,
        total_cents=totals.total_cents,
        expenses_cents=totals.expenses_cents,
        revision=None,
        closed_at=None,
        by_client=[
            ClientTotalsOut(
                client_id=c.client_id,
                name=c.name,
                scope=c.scope,
                base_cents=c.base_cents,
                invoice_count=c.invoice_count,
            )
            for c in totals.by_client
        ],
    )


def _first_visible_month(first: YearMonth | None, year: int) -> int:
    """El primer mes del año que se enseña: enero si la actividad empezó antes, el mes de su primer mes con actividad si fue ese año, y ninguno (13) si aún no había."""
    if first is None or first.year > year:
        return 13
    return 1 if first.year < year else first.month


class MonthlyClosingService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], clock: Clock) -> None:
        self.pool = pool
        self.clock = clock

    def _current(self) -> YearMonth:
        return YearMonth.of(today_in_madrid(self.clock))

    def _check_year(self, year: int, current: YearMonth) -> None:
        if not FIRST_YEAR <= year <= LAST_YEAR:
            raise errors.invalid_period()
        if year > current.year:
            raise errors.period_in_future()

    def _year(self, user: CurrentUser, year: int, current: YearMonth) -> list[_Month]:
        """Los meses del año que se enseñan, de enero a diciembre (o hasta el mes en curso), con el cierre guardado o el cálculo en vivo."""
        with user_transaction(self.pool, user.id, user.claims) as conn:
            created = conn.execute(CREATED_SQL).fetchone()
            first_invoice, first_expense = first_dates(conn)
            first = first_active_month(
                created["created_at"].astimezone(MADRID).date() if created else None, first_invoice, first_expense
            )
            stored = {row["month"]: row for row in conn.execute(STORED_SQL, {"year": year}).fetchall()}
            last_month = current.month if year == current.year else 12
            first_month = _first_visible_month(first, year)
            visible = sorted({*range(first_month, last_month + 1), *(m for m in stored if m <= last_month)})
            live = [YearMonth(year, m) for m in visible if m not in stored]
            built: dict[int, MonthTotals] = {}
            if live:
                start, end = window_bounds(live)
                invoices = invoices_between(conn, start, end)
                expenses = expenses_between(conn, start, end)
                built = {t.month: t for t in build_months(invoices, expenses, live)}

        months: list[_Month] = []
        for m in visible:
            if m in stored:
                months.append(_from_stored(stored[m]))
            else:
                status = "in_progress" if YearMonth(year, m) == current else "pending"
                months.append(_from_live(built[m], status))
        return months

    @staticmethod
    def _rows(months: list[_Month]) -> list[MonthRow]:
        rows: list[MonthRow] = []
        running = 0
        for m in months:
            running += m.total_cents
            rows.append(
                MonthRow(
                    month=m.month,
                    status=m.status,  # type: ignore[arg-type]
                    invoice_count=m.invoice_count,
                    national_cents=m.national_cents,
                    eu_cents=m.eu_cents,
                    non_eu_cents=m.non_eu_cents,
                    total_cents=m.total_cents,
                    expenses_cents=m.expenses_cents,
                    result_cents=m.total_cents - m.expenses_cents,
                    ytd_cents=running,
                    revision=m.revision,
                    closed_at=m.closed_at,
                )
            )
        return rows

    def year(self, user: CurrentUser, year: int | None) -> MonthlyClosings:
        current = self._current()
        year = current.year if year is None else year
        self._check_year(year, current)
        rows = self._rows(self._year(user, year, current))
        totals = YearTotals(
            invoice_count=sum(r.invoice_count for r in rows),
            national_cents=sum(r.national_cents for r in rows),
            eu_cents=sum(r.eu_cents for r in rows),
            non_eu_cents=sum(r.non_eu_cents for r in rows),
            total_cents=sum(r.total_cents for r in rows),
            expenses_cents=sum(r.expenses_cents for r in rows),
        )
        return MonthlyClosings(year=year, months=rows, totals=totals)

    def month(self, user: CurrentUser, year: int, month: int) -> MonthlyClosing:
        current = self._current()
        if not FIRST_YEAR <= year <= LAST_YEAR or not 1 <= month <= 12:
            raise errors.invalid_period()
        if YearMonth(year, month) > current:
            raise errors.period_in_future()
        months = self._year(user, year, current)
        rows = self._rows(months)
        for source, row in zip(months, rows, strict=True):
            if source.month == month:
                return MonthlyClosing(**row.model_dump(), year=year, by_client=source.by_client)
        raise errors.closing_not_found()
