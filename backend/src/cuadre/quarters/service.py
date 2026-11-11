"""El borrador del modelo 303 (SPEC-W-008 §5.3 y §5.4). Una lectura: no escribe nada, ni siquiera el registro de actividad (T8-07).

Valida el periodo ANTES de abrir una transacción (no se lee nada de un periodo inválido o futuro), lee con la identidad de la persona, construye el
borrador con el dominio puro y lo presenta. Los errores del dominio salen como problem+json; ninguno repite datos de la persona ni de sus documentos
(T8-06), y un tipo de IVA ilegible, que es un dato corrupto, deja además un aviso en el registro con el periodo y sin ningún importe ni nombre.
"""

import logging

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.db import user_transaction
from cuadre.quarters import errors
from cuadre.quarters.models import Modelo303, present
from cuadre.quarters.repository import expense_rows, invoice_rows
from cuadre.tax import (
    InvalidPeriod,
    PeriodInFuture,
    QuarterTooLarge,
    UnsupportedVatRate,
    build_modelo_303,
    quarter_bounds,
    quarter_of,
    validate_period,
)

logger = logging.getLogger("cuadre.quarters")


class QuarterService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], clock: Clock) -> None:
        self.pool = pool
        self.clock = clock

    def modelo_303(self, user: CurrentUser, year: int | None, quarter: int | None) -> Modelo303:
        """El 303 del trimestre pedido; sin año o sin trimestre se usan los de hoy en Europe/Madrid."""
        today = today_in_madrid(self.clock)
        current_year, current_quarter = quarter_of(today)
        year = current_year if year is None else year
        quarter = current_quarter if quarter is None else quarter
        try:
            validate_period(year, quarter, today)
        except InvalidPeriod:
            raise errors.invalid_period() from None
        except PeriodInFuture:
            raise errors.period_in_future() from None
        start, end = quarter_bounds(year, quarter)
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                invoices = invoice_rows(conn, start, end)
                expenses = expense_rows(conn, start, end)
            model = build_modelo_303(year, quarter, invoices, expenses, today)
        except QuarterTooLarge:
            raise errors.quarter_too_large() from None
        except UnsupportedVatRate:
            logger.warning("modelo_303_unsupported_vat_rate", extra={"year": year, "quarter": quarter})
            raise errors.unsupported_vat_rate() from None
        return present(model)
