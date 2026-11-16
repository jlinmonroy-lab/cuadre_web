"""El reporte mensual que ve la persona (SPEC-W-013 §5.3 y §5.4, D-01 a D-08). Una lectura: no escribe nada.

Las cifras del mes, del mes anterior y de la tendencia salen de `MonthlyClosingService` (la misma foto que `/mensual`, sin recalcular aparte); solo los gastos por
categoría se leen de la base de datos. Todo lo que decide una cifra son las reglas puras de `cuadre.reports.rules`.
"""

from dataclasses import asdict

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.closing.limits import FIRST_YEAR, LAST_YEAR
from cuadre.closing.models import MonthlyClosing
from cuadre.closing.rules import month_bounds
from cuadre.closing.service import MonthlyClosingService
from cuadre.closing.types import YearMonth
from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.db import user_transaction
from cuadre.reports import errors
from cuadre.reports.models import CategoryTotalOut, ComparisonOut, MonthlyReport, ScopeShareOut, TrendPoint
from cuadre.reports.repository import expenses_with_category
from cuadre.reports.rules import (
    PeriodBeforeActivity,
    ReportTooLarge,
    build_comparison,
    expenses_note,
    group_by_category,
    quarter_of,
    scope_shares,
    trend_window,
)
from cuadre.reports.types import MonthFigures


def _figures(item: MonthlyClosing) -> MonthFigures:
    return MonthFigures(item.year, item.month, item.status, item.total_cents, item.expenses_cents)


class MonthlyReportService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], clock: Clock) -> None:
        self.pool = pool
        self.clock = clock
        self.closings = MonthlyClosingService(pool, clock)

    def _listed(self, user: CurrentUser, year: int, month: int) -> dict[YearMonth, MonthlyClosing]:
        """Los meses que se enseñan del año del pedido y, si la tendencia o la comparación llegan al año anterior, también los de ese año."""
        listed = {YearMonth(i.year, i.month): i for i in self.closings.months_of(user, year)}
        if month <= 11 and year - 1 >= FIRST_YEAR:
            listed.update({YearMonth(i.year, i.month): i for i in self.closings.months_of(user, year - 1)})
        return listed

    def report(self, user: CurrentUser, year: int, month: int) -> MonthlyReport:
        current = YearMonth.of(today_in_madrid(self.clock))
        if not FIRST_YEAR <= year <= LAST_YEAR or not 1 <= month <= 12:
            raise errors.invalid_period()
        selected = YearMonth(year, month)
        if selected > current:
            raise errors.period_in_future()

        listed = self._listed(user, year, month)
        item = listed.get(selected)
        if item is None:
            raise errors.closing_not_found()
        try:
            window = trend_window(selected, min(listed))
        except PeriodBeforeActivity:
            raise errors.closing_not_found() from None

        start, end = month_bounds(selected)
        with user_transaction(self.pool, user.id, user.claims) as conn:
            expenses = expenses_with_category(conn, start, end)
        try:
            categories = group_by_category(expenses)
        except ReportTooLarge:
            raise errors.report_too_large() from None
        categories_total = sum(c.expenses_cents for c in categories)

        previous = listed.get(selected.previous())
        comparison = build_comparison(_figures(item), _figures(previous) if previous is not None else None)
        return MonthlyReport(
            **item.model_dump(),
            comparison=ComparisonOut(**asdict(comparison)) if comparison is not None else None,
            scopes=[
                ScopeShareOut(**asdict(s)) for s in scope_shares(item.national_cents, item.eu_cents, item.non_eu_cents)
            ],
            expenses_by_category=[CategoryTotalOut(**asdict(c)) for c in categories],
            expenses_by_category_total_cents=categories_total,
            expenses_note=expenses_note(categories_total, item.expenses_cents),
            trend=[
                TrendPoint(
                    year=ym.year,
                    month=ym.month,
                    status=listed[ym].status,
                    total_cents=listed[ym].total_cents,
                    expenses_cents=listed[ym].expenses_cents,
                    result_cents=listed[ym].result_cents,
                )
                for ym in window
                if ym in listed
            ],
            quarter=quarter_of(month),
            quarter_year=year,
        )
