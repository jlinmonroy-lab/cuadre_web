"""SPEC-W-010 hito 1 · Lo que las mutaciones dejaron sin cubrir de las funciones del gestor: carrera real del límite, anotaciones sobre lo de otro autónomo y tipos."""

import threading
import time
import uuid
from datetime import date

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from tests.rls.expenses_support import insert, manual
from tests.rls.invoices_support import code_of, issue, made, ready
from tests.support import Cast, Pool, apply_scenario, call, make_cast, new_document


def open_count(admin: Connection[DictRow], owner_id: object) -> int:
    row = admin.execute(
        "select count(*) as n from public.gestor_access where owner_id = %s and status in ('pending', 'active')",
        (owner_id,),
    ).fetchone()
    assert row is not None
    return int(row["n"])


def test_a_transaction_in_flight_holds_the_limit_for_the_next_one(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """Sin el cerrojo asesor, la segunda invitación vería 4 abiertas (la primera aún no se ha confirmado) y pasaría del límite."""
    for n in range(4):
        made(call(app_pool, cast.alicia, "invite_gestor_access", f"g{n}.{cast.alicia.email}"))
    inserted, release = threading.Event(), threading.Event()

    def first() -> None:
        with user_transaction(app_pool, cast.alicia.id) as conn:
            conn.execute("select app.invite_gestor_access(%s)", (f"first.{cast.alicia.email}",))
            inserted.set()
            release.wait(10)  # la transacción sigue abierta: aún no se ha confirmado

    holder = threading.Thread(target=first)
    holder.start()
    assert inserted.wait(10)
    outcome: dict[str, object] = {}
    waiter = threading.Thread(
        target=lambda: outcome.update(
            out=call(app_pool, cast.alicia, "invite_gestor_access", f"second.{cast.alicia.email}")
        )
    )
    waiter.start()
    time.sleep(0.6)  # con cerrojo, la segunda espera; sin él, ya habría terminado
    release.set()
    holder.join(10)
    waiter.join(10)
    out = outcome["out"]
    assert code_of(out) == "too_many_open_invitations"  # type: ignore[arg-type]
    assert open_count(admin, cast.alicia.id) == 5


def test_a_note_cannot_point_to_an_invoice_or_a_document_of_somebody_else(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    apply_scenario(app_pool, cast, "active")
    other = make_cast(admin)
    r = ready(admin, other.alicia)
    foreign_invoice = made(issue(app_pool, other.alicia, r.clients[("national", "business")], r.series, base=100_000))
    foreign_document = new_document(app_pool, other.alicia).id
    for kind, entity in (("invoice", foreign_invoice), ("document", foreign_document)):
        out = call(app_pool, cast.gina, "add_gestor_note", cast.alicia.id, "Mira esto", kind, entity)
        assert code_of(out) == "invalid_note" and out.detail == "entity", kind


def test_an_unknown_entity_type_is_invalid_note_even_if_the_id_exists_as_something_else(
    app_pool: Pool, cast: Cast
) -> None:
    apply_scenario(app_pool, cast, "active")
    document = new_document(
        app_pool, cast.alicia
    ).id  # existe y es de Alicia, pero el tipo «client» no es de los permitidos
    out = call(app_pool, cast.gina, "add_gestor_note", cast.alicia.id, "Mira esto", "client", document)
    assert code_of(out) == "invalid_note" and out.detail == "entity"


@pytest.mark.parametrize("kind", ["invoice", "expense", "document"])
def test_a_note_linked_to_each_allowed_kind_keeps_its_type_and_id(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, kind: str
) -> None:
    apply_scenario(app_pool, cast, "active")
    if kind == "expense":
        entity = insert(
            admin, manual(cast.alicia, date=date(2026, 3, 3), name="Gasto anotado", base=1_000, total=1_000)
        )
    elif kind == "document":
        entity = new_document(app_pool, cast.alicia).id
    else:
        r = ready(admin, cast.alicia)
        entity = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, base=100_000))
    note_id = made(call(app_pool, cast.gina, "add_gestor_note", cast.alicia.id, "Con enlace", kind, entity))
    row = admin.execute("select entity_type, entity_id from public.gestor_notes where id = %s", (note_id,)).fetchone()
    assert row == {"entity_type": kind, "entity_id": entity}
    assert uuid.UUID(str(entity))
