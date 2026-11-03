"""`cuadre.db.session`: la identidad llega a la base de datos y no se filtra entre peticiones (ADR-0003)."""

import os
import uuid

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import open_pool, service_transaction, user_transaction
from tests.support import Cast, Pool


def test_the_transaction_runs_as_authenticated_with_the_users_identity(app_pool: Pool, cast: Cast) -> None:
    with user_transaction(app_pool, cast.alicia.id) as conn:
        row = conn.execute("select current_user as u, auth.uid() as uid, auth.role() as r").fetchone()
    assert row == {"u": "authenticated", "uid": cast.alicia.id, "r": "authenticated"}


def test_extra_claims_are_visible_but_cannot_override_the_subject_or_the_role(app_pool: Pool, cast: Cast) -> None:
    claims = {"sub": str(cast.beto.id), "role": "service_role", "session_id": "s-1"}
    with user_transaction(app_pool, cast.alicia.id, claims) as conn:
        row = conn.execute(
            "select auth.uid() as uid, auth.role() as r, current_setting('request.jwt.claims')::jsonb ->> 'session_id' as s"
        ).fetchone()
    assert row == {"uid": cast.alicia.id, "r": "authenticated", "s": "s-1"}


def test_role_does_not_leak_to_the_next_request() -> None:
    """Con un pool de UNA conexión, la petición siguiente reutiliza la misma: el rol y las claims deben haberse ido."""
    pool = open_pool(os.environ["DATABASE_URL"], name="leak-check", min_size=1, max_size=1)
    try:
        with user_transaction(pool, uuid.uuid4()) as conn:
            assert conn.execute("select current_user as u").fetchone() == {"u": "authenticated"}
        with pool.connection() as conn:
            row = conn.execute(
                "select current_user as u, nullif(current_setting('request.jwt.claims', true), '') as claims"
            ).fetchone()
        assert row == {"u": "cuadre_app", "claims": None}
    finally:
        pool.close()


def test_the_role_does_not_leak_after_an_error() -> None:
    pool = open_pool(os.environ["DATABASE_URL"], name="leak-check-error", min_size=1, max_size=1)
    try:
        with pytest.raises(RuntimeError), user_transaction(pool, uuid.uuid4()):
            raise RuntimeError("fallo de la petición")
        with pool.connection() as conn:
            assert conn.execute("select current_user as u").fetchone() == {"u": "cuadre_app"}
    finally:
        pool.close()


def test_commits_on_success_and_rolls_back_on_error(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    def name() -> str:
        row = admin.execute("select display_name from public.profiles where id = %s", (cast.alicia.id,)).fetchone()
        assert row is not None
        return row["display_name"]

    with pytest.raises(RuntimeError), user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("update public.profiles set display_name = 'no persiste' where id = %s", (cast.alicia.id,))
        raise RuntimeError
    assert name() == "Alicia"

    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("update public.profiles set display_name = 'persiste' where id = %s", (cast.alicia.id,))
    assert name() == "persiste"


def test_an_invalid_user_id_never_reaches_the_database(app_pool: Pool) -> None:
    with pytest.raises(ValueError), user_transaction(app_pool, "no-es-un-uuid"):
        pass


def test_the_login_roles_cannot_read_anything_by_themselves(app_pool: Pool, service_pool: Pool) -> None:
    for pool in (app_pool, service_pool):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), pool.connection() as conn:
            conn.execute("select count(*) from public.profiles")


def test_service_transaction_runs_as_service_role_and_bypasses_rls(service_pool: Pool, cast: Cast) -> None:
    with service_transaction(service_pool) as conn:
        who = conn.execute("select current_user as u").fetchone()
        seen = conn.execute(
            "select count(*) as n from public.profiles where id = any(%s)", (list(cast.ids()),)
        ).fetchone()
    assert who == {"u": "service_role"}
    assert seen == {"n": 5}


@pytest.mark.pooler
def test_the_identity_survives_a_transaction_pooler(cast: Cast) -> None:
    """Supavisor en modo transacción: SET LOCAL ROLE y las claims deben funcionar igual (como en Supabase alojado)."""
    dsn = os.environ.get(
        "TEST_DATABASE_POOLER_URL", "postgresql://cuadre_app.pooler-dev:cuadre-dev-only@127.0.0.1:54329/postgres"
    )
    try:
        pool = open_pool(dsn, name="pooler", min_size=1, max_size=2)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de conexión equivale a «el pooler local no lo admite»
        pytest.skip(f"el pooler local no admite este usuario: {exc}")
    try:
        with user_transaction(pool, cast.alicia.id) as conn:
            row = conn.execute("select current_user as u, auth.uid() as uid").fetchone()
            assert row == {"u": "authenticated", "uid": cast.alicia.id}
            assert conn.execute("select count(*) as n from public.profiles").fetchone() == {"n": 1}
    finally:
        pool.close()
