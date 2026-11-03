"""AC-11 · El administrador gestiona cuentas pero no ve ningún dato financiero (D3)."""

import uuid

from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Pool, apply_scenario, attempt, call


def count(pool: Pool, person, sql: str, params: tuple = ()) -> int:
    out = attempt(pool, person, sql, params)
    assert not out.error, out.message
    return out.rows[0]["n"]


def test_the_admin_sees_account_metadata_but_no_financial_rows(app_pool: Pool, cast: Cast) -> None:
    """AC-11 · «Ningún dato financiero» significa de otras cuentas: la ficha propia (vacía) la crea el trigger de alta para todos."""
    apply_scenario(app_pool, cast, "active")
    adan = cast.adan

    profiles = attempt(app_pool, adan, "select id, email, role, status, created_at from public.profiles")
    assert cast.ids() <= {r["id"] for r in profiles.rows}

    others = "select count(*) as n from public.business_profiles where owner_id <> %s"
    assert count(app_pool, adan, others, (adan.id,)) == 0
    assert count(app_pool, adan, "select count(*) as n from public.business_profiles") == 1, "solo la suya"
    assert count(app_pool, adan, "select count(*) as n from public.gestor_access") == 0
    assert count(app_pool, adan, "select count(*) as n from public.activity_log where category <> 'account'") == 0
    assert count(app_pool, adan, "select count(*) as n from public.activity_log where category = 'account'") >= 5


def test_the_admin_changes_roles_and_it_is_logged(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert not call(app_pool, cast.adan, "admin_set_role", cast.beto.id, "gestor").error
    role = admin.execute("select role from public.profiles where id = %s", (cast.beto.id,)).fetchone()
    assert role is not None and role["role"] == "gestor"

    log = admin.execute(
        "select actor_id, actor_role, category, metadata from public.activity_log "
        "where owner_id = %s and action = 'account.role_changed'",
        (cast.beto.id,),
    ).fetchone()
    assert log is not None
    assert (log["actor_id"], log["actor_role"], log["category"]) == (cast.adan.id, "admin", "account")
    assert log["metadata"] == {"from": "usuario", "to": "gestor"}

    # Y el cambio rige en la petición siguiente de Beto, sin renovar nada.
    assert attempt(app_pool, cast.beto, "select private.app_role()::text as r").rows[0]["r"] == "gestor"


def test_the_admin_suspends_and_reactivates(app_pool: Pool, cast: Cast) -> None:
    assert not call(app_pool, cast.adan, "admin_set_status", cast.beto.id, "suspended").error
    assert attempt(app_pool, cast.beto, "select private.app_role()::text as r").rows[0]["r"] is None
    assert not call(app_pool, cast.adan, "admin_set_status", cast.beto.id, "active").error
    assert attempt(app_pool, cast.beto, "select private.app_role()::text as r").rows[0]["r"] == "usuario"


def test_the_admin_cannot_modify_themselves(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    for function, argument in (("admin_set_role", "usuario"), ("admin_set_status", "suspended")):
        out = call(app_pool, cast.adan, function, cast.adan.id, argument)
        assert (out.sqlstate, out.message) == ("P0001", "cannot_modify_self")
    row = admin.execute("select role, status from public.profiles where id = %s", (cast.adan.id,)).fetchone()
    assert row == {"role": "admin", "status": "active"}


def test_the_admin_target_must_exist(app_pool: Pool, cast: Cast) -> None:
    out = call(app_pool, cast.adan, "admin_set_role", uuid.uuid4(), "gestor")
    assert (out.sqlstate, out.message) == ("P0001", "target_not_found")


def test_a_suspended_admin_has_no_powers(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.adan.id,))
    assert call(app_pool, cast.adan, "admin_set_role", cast.beto.id, "gestor").sqlstate == "42501"
