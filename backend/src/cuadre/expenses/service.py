"""Los flujos de gastos (SPEC-W-003 §5.3 y §5.4): registrar desde un documento, anotar sin factura, listar, recategorizar y anular.

Reglas que importan:

* **Validar y registrar, atómico (T3-05).** `confirm` bloquea el documento, lo comprueba y lo registra en UNA transacción corta, sin esperas
  externas: nadie puede cambiar el documento entre la comprobación y el registro, y un fallo (también el `23505` del índice) lo revierte todo.
* **El orden es la seguridad.** Estado del documento -> comprobaciones -> reconocimiento de la sospecha -> registro. La base repite lo que
  la API acaba de comprobar (importes enteros, total coherente, reconocimiento, duplicados), así que un fallo de aquí no deja pasar nada.
* **La sospecha nunca valida ni exime (T3-06, NFR-07):** solo añade la exigencia de reconocerla.
* Nada de lo que contiene un gasto (nombre, NIF, número, importes, concepto) llega a un registro (NFR-11).
"""

from collections.abc import Callable
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.db import user_transaction
from cuadre.documents import errors as document_errors
from cuadre.expenses import cursor, errors, presentation, repository, validation
from cuadre.expenses.models import (
    ConfirmRequest,
    CreateExpense,
    Expense,
    ExpensePage,
    SetCategory,
    VoidResult,
)
from cuadre.validators import ExpenseCategory

LIST_DEFAULT_LIMIT = 50
LIST_MAX_LIMIT = 100


class ExpenseService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], clock: Clock) -> None:
        self.pool = pool
        self.clock = clock

    def _in_tx[T](self, user: CurrentUser, work: Callable[[Connection[DictRow]], T]) -> T:
        """Una transacción corta con la identidad de la persona. Los errores de las funciones `app.*` salen como problem+json."""
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                return work(conn)
        except psycopg.Error as exc:
            problem = repository.translate_db_error(exc)
            if problem is None:
                raise
            raise problem from None

    def _expense(self, conn: Connection[DictRow], expense_id: UUID) -> DictRow:
        row = repository.get(conn, expense_id)
        if row is None:
            raise errors.expense_not_found()
        return row

    # --- Registrar --------------------------------------------------------------------------------------------------------

    def confirm(self, user: CurrentUser, document_id: UUID, body: ConfirmRequest) -> Expense:
        def work(conn: Connection[DictRow]) -> Expense:
            document = repository.lock_document(conn, document_id)
            if document["status"] not in validation.REGISTRABLE_STATES:
                raise document_errors.document_wrong_state()

            result = validation.evaluate(conn, document, today_in_madrid(self.clock))
            if not result.can_register or result.values is None:
                raise errors.validation_failed([check.code.value for check in result.checks if not check.ok])
            if result.requires_acknowledgement and not body.acknowledge_suspicion:
                raise errors.suspicion_not_acknowledged()

            expense_id = repository.register(
                conn, document_id, body.category.value, result.values, body.acknowledge_suspicion
            )
            return presentation.to_expense(self._expense(conn, expense_id))

        return self._in_tx(user, work)

    def create(self, user: CurrentUser, body: CreateExpense) -> Expense:
        def work(conn: Connection[DictRow]) -> Expense:
            expense_id = repository.create_manual(
                conn, body.expense_date, body.concept, body.category.value, body.amount_cents
            )
            return presentation.to_expense(self._expense(conn, expense_id))

        return self._in_tx(user, work)

    # --- Leer -------------------------------------------------------------------------------------------------------------

    def get(self, user: CurrentUser, expense_id: UUID) -> Expense:
        return self._in_tx(user, lambda conn: presentation.to_expense(self._expense(conn, expense_id)))

    def list(
        self,
        user: CurrentUser,
        *,
        limit: int = LIST_DEFAULT_LIMIT,
        page: str | None = None,
        year: int | None = None,
        month: int | None = None,
        category: ExpenseCategory | None = None,
    ) -> ExpensePage:
        if month is not None and year is None:
            raise errors.month_needs_year()
        after = cursor.decode(page) if page is not None else None

        def work(conn: Connection[DictRow]) -> list[DictRow]:
            # Una fila de más para saber si hay otra página sin hacer una segunda consulta.
            return repository.list_page(
                conn,
                limit=limit + 1,
                after=after,
                year=year,
                month=month,
                category=category.value if category is not None else None,
            )

        rows = self._in_tx(user, work)
        shown = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = shown[-1]
            next_cursor = cursor.encode((last["expense_date"], last["created_at"], last["id"]))
        return ExpensePage(items=[presentation.to_summary(row) for row in shown], next_cursor=next_cursor)

    # --- Corregir y anular ------------------------------------------------------------------------------------------------

    def set_category(self, user: CurrentUser, expense_id: UUID, body: SetCategory) -> Expense:
        def work(conn: Connection[DictRow]) -> Expense:
            repository.set_category(conn, expense_id, body.category.value)
            return presentation.to_expense(self._expense(conn, expense_id))

        return self._in_tx(user, work)

    def void(self, user: CurrentUser, expense_id: UUID) -> VoidResult:
        def work(conn: Connection[DictRow]) -> VoidResult:
            document_status = repository.void(conn, expense_id)
            row = self._expense(conn, expense_id)
            return VoidResult(
                id=expense_id,
                document_id=row["document_id"],
                document_status=document_status,  # type: ignore[arg-type]
            )

        return self._in_tx(user, work)
