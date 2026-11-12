"""Los borradores de los modelos 303 y 130 (SPEC-W-008 y SPEC-W-009, §5.3 y §5.4). Una lectura: no escribe nada, ni siquiera el registro de actividad (T8-07).

Valida el periodo ANTES de abrir una transacción (no se lee nada de un periodo inválido o futuro), lee con la identidad de la persona, construye el
borrador con el dominio puro y lo presenta. Los errores del dominio salen como problem+json; ninguno repite datos de la persona ni de sus documentos
(T8-06), y un tipo de IVA ilegible, que es un dato corrupto, deja además un aviso en el registro con el periodo y sin ningún importe ni nombre.
"""

import logging
from collections.abc import Callable
from datetime import date

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.db import user_transaction
from cuadre.quarters import errors
from cuadre.quarters.models import Modelo130, Modelo303, present, present_130
from cuadre.quarters.repository import cost_rows, expense_rows, income_rows, invoice_rows
from cuadre.tax import (
    InvalidPeriod,
    PeriodInFuture,
    QuarterTooLarge,
    UnsupportedVatRate,
    build_modelo_130,
    build_modelo_303,
    quarter_bounds,
    quarter_of,
    validate_period,
    year_start,
)

logger = logging.getLogger("cuadre.quarters")


class QuarterService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], clock: Clock) -> None:
        self.pool = pool
        self.clock = clock

    def _period(self, year: int | None, quarter: int | None) -> tuple[date, int, int]:
        """El periodo pedido (por defecto, el de hoy en Europe/Madrid) ya validado: se responde antes de leer nada."""
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
        return today, year, quarter

    def resolve_period(self, year: int | None, quarter: int | None) -> tuple[int, int]:
        """El año y el trimestre pedidos (por defecto, los de hoy en Madrid), ya validados: lo usa el gestor para registrar el periodo antes de leer."""
        _, resolved_year, resolved_quarter = self._period(year, quarter)
        return resolved_year, resolved_quarter

    def modelo_303(
        self,
        user: CurrentUser,
        year: int | None,
        quarter: int | None,
        *,
        on_read: Callable[[Connection[DictRow]], None] | None = None,
    ) -> Modelo303:
        """El 303 del trimestre pedido; sin año o sin trimestre se usan los de hoy en Europe/Madrid. `on_read` (solo el gestor) se ejecuta en la misma
        transacción ANTES de leer: ahí se comprueba el vínculo y se registra la lectura."""
        today, year, quarter = self._period(year, quarter)
        start, end = quarter_bounds(year, quarter)
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                if on_read is not None:
                    on_read(conn)
                invoices = invoice_rows(conn, start, end)
                expenses = expense_rows(conn, start, end)
            model = build_modelo_303(year, quarter, invoices, expenses, today)
        except QuarterTooLarge:
            raise errors.quarter_too_large() from None
        except UnsupportedVatRate:
            logger.warning("modelo_303_unsupported_vat_rate", extra={"year": year, "quarter": quarter})
            raise errors.unsupported_vat_rate() from None
        return present(model)

    def modelo_130(
        self,
        user: CurrentUser,
        year: int | None,
        quarter: int | None,
        *,
        on_read: Callable[[Connection[DictRow]], None] | None = None,
    ) -> Modelo130:
        """El 130 del trimestre pedido, acumulado desde el 1 de enero; mismo periodo por defecto que el 303. No lee las líneas de IVA. `on_read`: como en el 303."""
        today, year, quarter = self._period(year, quarter)
        _, end = quarter_bounds(year, quarter)
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                if on_read is not None:
                    on_read(conn)
                incomes = income_rows(conn, year_start(year), end)
                costs = cost_rows(conn, year_start(year), end)
            model = build_modelo_130(year, quarter, incomes, costs, today)
        except QuarterTooLarge:
            raise errors.period_too_large() from None
        return present_130(model)
