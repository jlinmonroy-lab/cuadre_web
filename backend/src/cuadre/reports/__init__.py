"""Reporte mensual visual (SPEC-W-013, RF-014): las cifras que decide el servidor para cada gráfico. Python puro, sin base de datos y sin reloj.

El repositorio, el servicio y la API llegan en los siguientes hitos de la spec.
"""

from cuadre.reports.rules import (
    BASIS_POINTS,
    EXPENSES_NOTE,
    PeriodBeforeActivity,
    ReportTooLarge,
    build_comparison,
    expense_cost,
    expenses_note,
    group_by_category,
    quarter_of,
    scope_shares,
    share_bp,
    trend_window,
    variation_bp,
)
from cuadre.reports.types import CategorisedExpense, CategoryTotal, Comparison, MonthFigures, MonthStatus, ScopeShare

__all__ = [
    "BASIS_POINTS",
    "EXPENSES_NOTE",
    "CategorisedExpense",
    "CategoryTotal",
    "Comparison",
    "MonthFigures",
    "MonthStatus",
    "PeriodBeforeActivity",
    "ReportTooLarge",
    "ScopeShare",
    "build_comparison",
    "expense_cost",
    "expenses_note",
    "group_by_category",
    "quarter_of",
    "scope_shares",
    "share_bp",
    "trend_window",
    "variation_bp",
]
