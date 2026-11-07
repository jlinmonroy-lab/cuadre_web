"""AC-08, T3-05 · Validar y registrar es atómico: dos peticiones a la vez nunca dejan dos gastos de la misma factura ni dos del mismo documento.

Las pruebas con una transacción sin confirmar son deterministas: la segunda petición valida (no ve lo no confirmado), llega al índice o al
cerrojo del documento, espera y, cuando la primera confirma, pierde. Las de hilos libres comprueban el resultado, que es el mismo sea cual sea el orden.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from cuadre.expenses import repository, validation
from tests.documents.conftest import Api, db_row
from tests.expenses.support import all_expenses, confirm, live_expenses, read
from tests.support import Person, Pool


def register_without_committing(conn: Connection[DictRow], document_id: UUID) -> None:
    """Lo mismo que hace `confirm`, pero dejando la transacción abierta en manos de la prueba."""
    row = repository.lock_document(conn, document_id)
    result = validation.evaluate(conn, row, date(2026, 11, 7))
    assert result.values is not None
    repository.register(conn, document_id, "software", result.values, False)


def run_in_thread(target: Any) -> threading.Thread:
    thread = threading.Thread(target=target)
    return thread


def test_ac08_two_documents_with_the_same_invoice_leave_one_expense_and_a_409(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok", "invoice_ok")
    first, second = api.read(alicia), api.read(alicia)
    outcome: dict[str, Any] = {}
    waiter = run_in_thread(lambda: outcome.update(response=confirm(api, alicia, second)))

    with user_transaction(app_pool, alicia.id) as conn:
        register_without_committing(conn, first)  # aún sin confirmar
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=20)

    assert still_waiting, "la segunda confirmación no esperó a la primera"
    response = outcome["response"]
    assert response.status_code == 409 and response.json()["code"] == "duplicate_expense", response.text
    assert [row["document_id"] for row in live_expenses(admin, alicia)] == [first]
    assert db_row(admin, second)["status"] == "review", "el perdedor queda en revisión, intacto"


def test_two_confirmations_of_the_same_document_register_it_once(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    outcome: dict[str, Any] = {}
    waiter = run_in_thread(lambda: outcome.update(response=confirm(api, alicia, document_id)))

    with user_transaction(app_pool, alicia.id) as conn:
        register_without_committing(conn, document_id)
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=20)

    assert still_waiting
    response = outcome["response"]
    assert response.status_code == 409 and response.json()["code"] == "document_wrong_state", response.text
    assert len(all_expenses(admin, alicia)) == 1


def test_many_simultaneous_confirmations_of_one_document_leave_exactly_one_expense(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: confirm(api, alicia, document_id), range(6)))

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409, 409, 409, 409, 409], statuses
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {"document_wrong_state"}
    assert len(all_expenses(admin, alicia)) == 1


def test_two_documents_with_the_same_invoice_confirmed_at_once_leave_one_expense(
    api: Api, admin: Connection[DictRow]
) -> None:
    """Sin sincronizar: si la segunda valida después de que la primera confirme falla `not_duplicate` (422); si llega a la vez, el índice (409)."""
    alicia = api.cast.alicia
    api.script("invoice_ok", "invoice_ok")
    first, second = api.read(alicia), api.read(alicia)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda d: confirm(api, alicia, d), (first, second)))

    winners = [r for r in responses if r.status_code == 201]
    losers = [r for r in responses if r.status_code != 201]
    assert len(winners) == 1 and len(losers) == 1, [r.status_code for r in responses]
    assert (losers[0].status_code, losers[0].json()["code"]) in {(409, "duplicate_expense"), (422, "validation_failed")}
    assert len(live_expenses(admin, alicia)) == 1


def test_an_expense_registered_by_one_person_never_blocks_the_same_invoice_for_another(api: Api) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    people: list[Person] = [alicia, beto]
    api.script("invoice_ok", "invoice_ok")
    documents = [api.read(person) for person in people]
    for person, document_id in zip(people, documents, strict=True):
        assert confirm(api, person, document_id).status_code == 201
