"""AC-12 · El registro de actividad solo admite inserciones, y solo a través de `private.log_activity`."""

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import service_transaction
from tests.support import Cast, Pool, attempt


def a_row_id(admin: Connection[DictRow], cast: Cast) -> int:
    row = admin.execute("select id from public.activity_log where owner_id = %s limit 1", (cast.alicia.id,)).fetchone()
    assert row is not None
    return row["id"]


@pytest.mark.parametrize(
    "statement",
    ["update public.activity_log set action = 'x' where id = %s", "delete from public.activity_log where id = %s"],
)
def test_not_even_the_database_owner_can_change_a_row(admin: Connection[DictRow], cast: Cast, statement: str) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="activity_log_is_append_only"):
        admin.execute(statement, (a_row_id(admin, cast),))


def test_not_even_the_database_owner_can_truncate(admin: Connection[DictRow]) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="activity_log_is_append_only"):
        admin.execute("truncate public.activity_log")


def test_service_role_cannot_change_a_row(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    row_id = a_row_id(admin, cast)
    with pytest.raises(psycopg.Error), service_transaction(service_pool) as conn:
        conn.execute("update public.activity_log set action = 'x' where id = %s", (row_id,))


@pytest.mark.parametrize("who", ["alicia", "gina", "adan"])
def test_nobody_inserts_directly(app_pool: Pool, cast: Cast, who: str) -> None:
    out = attempt(app_pool, cast[who], "insert into public.activity_log (category, action) values ('data', 'forged')")
    assert out.sqlstate == "42501"


@pytest.mark.parametrize("who", ["alicia", "gina", "adan"])
def test_nobody_can_call_log_activity_to_forge_entries(app_pool: Pool, cast: Cast, who: str) -> None:
    out = attempt(
        app_pool,
        cast[who],
        "select private.log_activity('data', null, null, %s, 'forged', null, null, '{}'::jsonb)",
        (cast.beto.id,),
    )
    assert out.sqlstate == "42501"


def test_service_role_logs_through_the_function(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    with service_transaction(service_pool) as conn:
        conn.execute(
            "select private.log_activity('data', null, null, %s, 'job.check', 'job', 'x', '{}'::jsonb)",
            (cast.alicia.id,),
        )
    row = admin.execute(
        "select category, actor_id from public.activity_log where owner_id = %s and action = 'job.check'",
        (cast.alicia.id,),
    ).fetchone()
    assert row == {"category": "data", "actor_id": None}


def test_a_failed_transition_leaves_no_log(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """La acción y su registro van en la misma transacción: si la acción falla, no queda rastro de ella."""
    before = admin.execute("select count(*) as n from public.activity_log").fetchone()
    out = attempt(app_pool, cast.adan, "select app.admin_set_role(%s, 'gestor')", (cast.adan.id,))
    assert out.error
    after = admin.execute("select count(*) as n from public.activity_log").fetchone()
    assert before is not None and after is not None and after["n"] >= before["n"]
    assert (
        admin.execute(
            "select 1 from public.activity_log where actor_id = %s and action = 'account.role_changed'", (cast.adan.id,)
        ).fetchone()
        is None
    )
