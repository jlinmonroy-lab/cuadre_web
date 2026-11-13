"""AC-13 y AC-16 · Las tablas `reminder_settings` y `reminder_log` y sus funciones (SPEC-W-014 §5.2, D-01, D-03).

Ninguna tabla se escribe directamente: el usuario guarda sus ajustes con `app.set_reminder_settings`, y solo el job (`service_role`) reserva y cierra
recordatorios con `private.reminder_claim` y `private.reminder_mark`. `service_role` no puede borrar, así que un envío fallido deja la fila en `failed`
y se reclama de nuevo. La visibilidad por rol la prueba además la matriz de RLS.
"""

import threading
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import service_transaction
from tests.support import Cast, Pool, attempt, call

PERIOD = "2026-Q4"
KIND = "quarter_deadline"


def settings_of(admin: Connection[DictRow], owner: Any) -> dict[str, Any] | None:
    return admin.execute(
        "select enabled, lead_days from public.reminder_settings where owner_id = %s", (owner,)
    ).fetchone()


def log_of(admin: Connection[DictRow], owner: Any, period: str = PERIOD) -> dict[str, Any] | None:
    return admin.execute(
        "select status, sent_at, claimed_at from public.reminder_log where owner_id = %s and period = %s and kind = %s",
        (owner, period, KIND),
    ).fetchone()


def claim(pool: Pool, owner: Any, period: str = PERIOD) -> bool:
    with service_transaction(pool) as conn:
        row = conn.execute("select private.reminder_claim(%s, %s, %s) as ok", (owner, period, KIND)).fetchone()
    assert row is not None
    return row["ok"]


def mark(pool: Pool, owner: Any, sent: bool, period: str = PERIOD) -> None:
    with service_transaction(pool) as conn:
        conn.execute("select private.reminder_mark(%s, %s, %s, %s)", (owner, period, KIND, sent))


# --- Ajustes del usuario ---------------------------------------------------------------------------------------------------------------


def test_a_user_saves_and_changes_their_settings(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert settings_of(admin, cast.alicia.id) is None  # sin fila = valores por defecto (D-01)
    assert not call(app_pool, cast.alicia, "set_reminder_settings", True, 14).error
    assert settings_of(admin, cast.alicia.id) == {"enabled": True, "lead_days": 14}
    assert not call(app_pool, cast.alicia, "set_reminder_settings", False, 3).error  # upsert: no duplica
    assert settings_of(admin, cast.alicia.id) == {"enabled": False, "lead_days": 3}
    count = admin.execute("select count(*) as n from public.reminder_settings where owner_id = %s", (cast.alicia.id,))
    assert count.fetchone() == {"n": 1}
    assert settings_of(admin, cast.beto.id) is None


@pytest.mark.parametrize("days", [1, 10, 30])
def test_lead_days_the_function_accepts(app_pool: Pool, admin: Connection[DictRow], cast: Cast, days: int) -> None:
    assert not call(app_pool, cast.alicia, "set_reminder_settings", True, days).error
    assert settings_of(admin, cast.alicia.id) == {"enabled": True, "lead_days": days}


@pytest.mark.parametrize("days", [0, -1, 31, None])
def test_lead_days_outside_one_to_thirty_are_refused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, days: int | None
) -> None:
    out = call(app_pool, cast.alicia, "set_reminder_settings", True, days)
    assert (out.sqlstate, out.message) == ("P0001", "invalid_lead_days")
    assert settings_of(admin, cast.alicia.id) is None


@pytest.mark.parametrize("who", ["gina", "adan"])
def test_only_a_user_saves_settings(app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str) -> None:
    assert call(app_pool, cast[who], "set_reminder_settings", True, 10).sqlstate == "42501"
    assert settings_of(admin, cast[who].id) is None


def test_a_suspended_account_cannot_save_settings(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert call(app_pool, cast.alicia, "set_reminder_settings", True, 10).sqlstate == "42501"
    assert settings_of(admin, cast.alicia.id) is None


def test_saving_only_ever_touches_the_callers_row(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("insert into public.reminder_settings (owner_id, lead_days) values (%s, 20)", (cast.beto.id,))
    assert not call(app_pool, cast.alicia, "set_reminder_settings", False, 5).error
    assert settings_of(admin, cast.beto.id) == {"enabled": True, "lead_days": 20}


# --- Nadie escribe las tablas directamente -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_writes_the_tables_directly_not_even_the_owner(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    admin.execute("insert into public.reminder_settings (owner_id) values (%s)", (cast.alicia.id,))
    admin.execute(
        "insert into public.reminder_log (owner_id, period, kind) values (%s, %s, %s)", (cast.alicia.id, PERIOD, KIND)
    )
    person = cast[who]
    statements = (
        ("insert into public.reminder_settings (owner_id) values (%s)", (person.id,)),
        ("update public.reminder_settings set lead_days = 3", None),
        ("delete from public.reminder_settings", None),
        (
            "insert into public.reminder_log (owner_id, period, kind) values (%s, '2027-Q1', 'quarter_deadline')",
            (person.id,),
        ),
        ("update public.reminder_log set status = 'sent', sent_at = now()", None),
        ("delete from public.reminder_log", None),
    )
    for sql, params in statements:
        assert attempt(app_pool, person, sql, params).sqlstate == "42501", sql
    assert settings_of(admin, cast.alicia.id) == {"enabled": True, "lead_days": 10}
    assert log_of(admin, cast.alicia.id) is not None and log_of(admin, cast.alicia.id)["status"] == "pending"  # type: ignore[index]


@pytest.mark.parametrize("table", ["reminder_settings", "reminder_log"])
def test_the_tables_have_forced_rls_and_service_role_has_no_direct_access(
    admin: Connection[DictRow], table: str
) -> None:
    row = admin.execute(
        "select relrowsecurity as rls, relforcerowsecurity as forced from pg_class where oid = %s::regclass",
        (f"public.{table}",),
    ).fetchone()
    assert row == {"rls": True, "forced": True}
    for role, privileges in (("authenticated", {"SELECT": True}), ("anon", {}), ("service_role", {})):
        for p in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            found = admin.execute(
                "select has_table_privilege(%s, %s, %s) as ok", (role, f"public.{table}", p)
            ).fetchone()
            assert found is not None and found["ok"] is privileges.get(p, False), (role, p)


@pytest.mark.parametrize("table", ["reminder_settings", "reminder_log"])
def test_there_is_exactly_one_read_policy_and_none_for_the_gestor_or_the_admin(
    admin: Connection[DictRow], table: str
) -> None:
    found = admin.execute(
        "select policyname, cmd from pg_policies where schemaname = 'public' and tablename = %s order by 1", (table,)
    ).fetchall()
    assert [(r["policyname"], r["cmd"]) for r in found] == [(f"{table}_select_owner", "SELECT")]


def test_service_role_cannot_write_the_log_directly(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege), service_transaction(service_pool) as conn:
        conn.execute(
            "insert into public.reminder_log (owner_id, period, kind) values (%s, %s, %s)",
            (cast.alicia.id, PERIOD, KIND),
        )
    assert log_of(admin, cast.alicia.id) is None


# --- Reservar y cerrar (job) ----------------------------------------------------------------------------------------------------------------


def test_the_first_claim_wins_and_the_second_is_refused(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    assert claim(service_pool, cast.alicia.id) is True
    assert claim(service_pool, cast.alicia.id) is False  # en curso
    row = log_of(admin, cast.alicia.id)
    assert row is not None and row["status"] == "pending" and row["sent_at"] is None


def test_a_sent_reminder_is_never_claimed_again(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert claim(service_pool, cast.alicia.id) is True
    mark(service_pool, cast.alicia.id, True)
    row = log_of(admin, cast.alicia.id)
    assert row is not None and row["status"] == "sent" and row["sent_at"] is not None
    assert claim(service_pool, cast.alicia.id) is False
    mark(service_pool, cast.alicia.id, False)  # ya no está pendiente: no cambia nada
    row = log_of(admin, cast.alicia.id)
    assert row is not None and row["status"] == "sent"
    count = admin.execute("select count(*) as n from public.reminder_log where owner_id = %s", (cast.alicia.id,))
    assert count.fetchone() == {"n": 1}


def test_a_failed_reminder_is_claimed_again_without_deleting_anything(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    assert claim(service_pool, cast.alicia.id) is True
    mark(service_pool, cast.alicia.id, False)
    row = log_of(admin, cast.alicia.id)
    assert row is not None and row["status"] == "failed" and row["sent_at"] is None
    assert claim(service_pool, cast.alicia.id) is True
    row = log_of(admin, cast.alicia.id)
    assert row is not None and row["status"] == "pending"
    mark(service_pool, cast.alicia.id, True)
    assert claim(service_pool, cast.alicia.id) is False


def test_an_abandoned_pending_reservation_is_reclaimed_after_fifteen_minutes(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    assert claim(service_pool, cast.alicia.id) is True
    admin.execute(
        "update public.reminder_log set claimed_at = now() - interval '14 minutes' where owner_id = %s",
        (cast.alicia.id,),
    )
    assert claim(service_pool, cast.alicia.id) is False
    admin.execute(
        "update public.reminder_log set claimed_at = now() - interval '16 minutes' where owner_id = %s",
        (cast.alicia.id,),
    )
    assert claim(service_pool, cast.alicia.id) is True


def test_each_person_and_period_has_its_own_reservation(service_pool: Pool, cast: Cast) -> None:
    assert claim(service_pool, cast.alicia.id) is True
    assert claim(service_pool, cast.beto.id) is True
    assert claim(service_pool, cast.alicia.id, "2027-Q1") is True


def test_two_simultaneous_claims_let_exactly_one_send(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    results: list[bool] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        results.append(claim(service_pool, cast.alicia.id))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False, True]
    count = admin.execute("select count(*) as n from public.reminder_log where owner_id = %s", (cast.alicia.id,))
    assert count.fetchone() == {"n": 1}


def test_the_job_functions_are_not_callable_by_users(app_pool: Pool, cast: Cast) -> None:
    for who in ("alicia", "gina", "adan"):
        claimed = attempt(
            app_pool, cast[who], "select private.reminder_claim(%s, %s, %s)", (cast.alicia.id, PERIOD, KIND)
        )
        marked = attempt(
            app_pool, cast[who], "select private.reminder_mark(%s, %s, %s, true)", (cast.alicia.id, PERIOD, KIND)
        )
        assert claimed.sqlstate == "42501" and marked.sqlstate == "42501", who


# --- Las CHECK, por nombre ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        (("2026-Q5", KIND, "pending", None), "reminder_log_period_format"),
        (("2026-4", KIND, "pending", None), "reminder_log_period_format"),
        ((PERIOD, "monthly", "pending", None), "reminder_log_kind_known"),
        ((PERIOD, KIND, "queued", None), "reminder_log_status_known"),
        ((PERIOD, KIND, "sent", None), "reminder_log_sent_at_iff_sent"),
        ((PERIOD, KIND, "pending", "now()"), "reminder_log_sent_at_iff_sent"),
    ],
)
def test_the_log_checks(admin: Connection[DictRow], cast: Cast, fields: tuple[Any, ...], constraint: str) -> None:
    period, kind, status, sent_at = fields
    sent = sent_at or "null"
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        admin.execute(
            f"insert into public.reminder_log (owner_id, period, kind, status, sent_at) values (%s, %s, %s, %s, {sent})",
            (cast.alicia.id, period, kind, status),
        )
    assert caught.value.diag.constraint_name == constraint


@pytest.mark.parametrize("days", [0, 31])
def test_the_settings_check(admin: Connection[DictRow], cast: Cast, days: int) -> None:
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        admin.execute(
            "insert into public.reminder_settings (owner_id, lead_days) values (%s, %s)", (cast.alicia.id, days)
        )
    assert caught.value.diag.constraint_name == "reminder_settings_lead_days_range"


def test_the_log_is_unique_per_owner_period_and_kind(admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute(
        "insert into public.reminder_log (owner_id, period, kind) values (%s, %s, %s)", (cast.alicia.id, PERIOD, KIND)
    )
    with pytest.raises(psycopg.errors.UniqueViolation) as caught:
        admin.execute(
            "insert into public.reminder_log (owner_id, period, kind) values (%s, %s, %s)",
            (cast.alicia.id, PERIOD, KIND),
        )
    assert caught.value.diag.constraint_name == "reminder_log_once"


def test_both_rows_go_away_with_the_account(admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("insert into public.reminder_settings (owner_id) values (%s)", (cast.beto.id,))
    admin.execute(
        "insert into public.reminder_log (owner_id, period, kind) values (%s, %s, %s)", (cast.beto.id, PERIOD, KIND)
    )
    admin.execute("delete from auth.users where id = %s", (cast.beto.id,))
    assert settings_of(admin, cast.beto.id) is None and log_of(admin, cast.beto.id) is None


# --- Candidatos del job (SPEC-W-014 §5.2) --------------------------------------------------------------------------------------------------


def candidates(pool: Pool) -> dict[Any, dict[str, Any]]:
    with service_transaction(pool) as conn:
        rows = conn.execute("select * from private.reminder_candidates()").fetchall()
    return {row["owner_id"]: row for row in rows}


def test_candidates_are_the_active_users_with_their_settings_or_the_defaults(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    from cuadre.jobs.reminders import DEFAULT_ENABLED, DEFAULT_LEAD_DAYS

    admin.execute(
        "insert into public.reminder_settings (owner_id, enabled, lead_days) values (%s, false, 3)", (cast.beto.id,)
    )
    found = candidates(service_pool)
    assert found[cast.alicia.id]["email"] == cast.alicia.email
    assert (found[cast.alicia.id]["enabled"], found[cast.alicia.id]["lead_days"]) == (
        DEFAULT_ENABLED,
        DEFAULT_LEAD_DAYS,
    )
    assert (found[cast.beto.id]["enabled"], found[cast.beto.id]["lead_days"]) == (False, 3)


def test_candidates_leave_out_gestores_admins_and_suspended_accounts(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.beto.id,))
    found = candidates(service_pool)
    assert cast.alicia.id in found
    for person in (cast.beto, cast.gina, cast.gus, cast.adan):
        assert person.id not in found


def test_candidates_are_not_callable_by_users_or_anon(app_pool: Pool, cast: Cast) -> None:
    for who in ("alicia", "gina", "adan"):
        out = attempt(app_pool, cast[who], "select * from private.reminder_candidates()")
        assert out.sqlstate == "42501", who
