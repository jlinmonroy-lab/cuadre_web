"""Cierre mensual (SPEC-W-012, RF-012): qué meses toca cerrar y cómo se calculan sus totales por ámbito y por cliente. Python puro, sin base de datos y sin reloj.

El repositorio, el servicio de la API y el job llegan en los siguientes hitos de la spec.
"""

from cuadre.closing.limits import CLOSING_MAX_DOCUMENTS, FIRST_YEAR, LAST_YEAR, MAX_WINDOW_MONTHS, WINDOW_MONTHS
from cuadre.closing.rules import (
    ClosingTooLarge,
    InvalidMonth,
    build_month,
    build_months,
    closing_window,
    explicit_window,
    first_active_month,
    month_bounds,
    payload_of,
    window_bounds,
)
from cuadre.closing.types import ClientTotals, MonthExpense, MonthInvoice, MonthTotals, Scope, YearMonth

__all__ = [
    "CLOSING_MAX_DOCUMENTS",
    "FIRST_YEAR",
    "LAST_YEAR",
    "MAX_WINDOW_MONTHS",
    "WINDOW_MONTHS",
    "ClientTotals",
    "ClosingTooLarge",
    "InvalidMonth",
    "MonthExpense",
    "MonthInvoice",
    "MonthTotals",
    "Scope",
    "YearMonth",
    "build_month",
    "build_months",
    "closing_window",
    "explicit_window",
    "first_active_month",
    "month_bounds",
    "payload_of",
    "window_bounds",
]
