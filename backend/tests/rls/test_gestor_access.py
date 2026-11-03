"""AC-08, AC-09, AC-10 · El acceso del gestor: solo lectura, solo con vínculo activo y revocable al instante (CONF-001 a)."""

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Pool, apply_scenario, attempt, call, invite, visible_owners


def reads_alicia(pool: Pool, cast: Cast, reader_key: str = "gina") -> bool:
    return cast.alicia.id in visible_owners(pool, cast[reader_key], "business_profiles", "owner_id")


def access_log(admin: Connection[DictRow], cast: Cast) -> list[str]:
    rows = admin.execute(
        "select action from public.activity_log where owner_id = %s and category = 'access' order by id",
        (cast.alicia.id,),
    ).fetchall()
    return [r["action"] for r in rows]


def test_an_active_link_reads_only_the_client(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """AC-08."""
    admin.execute("update public.business_profiles set tax_id = 'TEST-ALICIA' where owner_id = %s", (cast.alicia.id,))
    admin.execute("update public.business_profiles set tax_id = 'TEST-BETO' where owner_id = %s", (cast.beto.id,))
    apply_scenario(app_pool, cast, "active")

    out = attempt(
        app_pool, cast.gina, "select owner_id, tax_id from public.business_profiles order by tax_id nulls last"
    )
    seen = {row["owner_id"]: row["tax_id"] for row in out.rows}
    assert seen[cast.alicia.id] == "TEST-ALICIA"
    assert cast.beto.id not in seen
    assert set(seen) == {cast.alicia.id, cast.gina.id}

    profiles = visible_owners(app_pool, cast.gina, "profiles", "id")
    assert profiles == {cast.gina.id, cast.alicia.id}


def test_pending_invitation_gives_no_access(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "pending")
    assert not reads_alicia(app_pool, cast)


def test_the_full_lifecycle_and_its_audit_trail(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """AC-09 · pendiente -> activo -> revocado, con el mismo gestor y sin volver a iniciar sesión."""
    link = invite(app_pool, cast.alicia, cast.gina)
    assert not reads_alicia(app_pool, cast)

    assert not call(app_pool, cast.gina, "accept_gestor_access", link).error
    assert reads_alicia(app_pool, cast)

    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert not reads_alicia(app_pool, cast), "tras revocar, el gestor debe quedarse sin acceso en la petición siguiente"

    assert access_log(admin, cast) == ["gestor_access.accepted", "gestor_access.revoked"]
    row = admin.execute("select status, revoked_at from public.gestor_access where id = %s", (link,)).fetchone()
    assert row is not None and row["status"] == "revoked" and row["revoked_at"] is not None


def test_a_declined_invitation_gives_no_access(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    apply_scenario(app_pool, cast, "declined")
    assert not reads_alicia(app_pool, cast)
    assert access_log(admin, cast) == ["gestor_access.declined"]


def test_changing_the_gestor_role_cuts_access_immediately(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    assert reads_alicia(app_pool, cast)
    assert not call(app_pool, cast.adan, "admin_set_role", cast.gina.id, "usuario").error
    assert not reads_alicia(app_pool, cast)


def test_suspending_the_gestor_cuts_access_but_keeps_their_own_profile_readable(app_pool: Pool, cast: Cast) -> None:
    """La API necesita leer el perfil propio de una cuenta suspendida para responder 403 account_suspended."""
    apply_scenario(app_pool, cast, "active")
    assert not call(app_pool, cast.adan, "admin_set_status", cast.gina.id, "suspended").error
    assert not reads_alicia(app_pool, cast)
    out = attempt(app_pool, cast.gina, "select status from public.profiles where id = %s", (cast.gina.id,))
    assert [r["status"] for r in out.rows] == ["suspended"]


def test_a_gestor_cannot_write_in_the_users_tables(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """AC-10."""
    link = apply_scenario(app_pool, cast, "active")
    gina, alicia = cast.gina, cast.alicia
    attempts = [
        attempt(
            app_pool, gina, "update public.business_profiles set legal_name = 'x' where owner_id = %s", (alicia.id,)
        ),
        attempt(app_pool, gina, "delete from public.business_profiles where owner_id = %s", (alicia.id,)),
        attempt(app_pool, gina, "insert into public.business_profiles (owner_id) values (%s)", (alicia.id,)),
        attempt(app_pool, gina, "update public.profiles set display_name = 'x' where id = %s", (alicia.id,)),
        attempt(app_pool, gina, "update public.gestor_access set status = 'revoked' where id = %s", (link,)),
        attempt(app_pool, gina, "delete from public.gestor_access where id = %s", (link,)),
        attempt(
            app_pool,
            gina,
            "insert into public.gestor_access (owner_id, gestor_email) values (%s, %s)",
            (alicia.id, "x@example.test"),
        ),
    ]
    assert all(a.blocked for a in attempts), [a.message for a in attempts]
    assert reads_alicia(app_pool, cast), "el vínculo sigue activo"
    row = admin.execute("select legal_name from public.business_profiles where owner_id = %s", (alicia.id,)).fetchone()
    assert row is not None and row["legal_name"] is None


# --- Reglas de las funciones de transición ---------------------------------------------------------------------------------


def test_only_the_addressed_gestor_can_accept(app_pool: Pool, cast: Cast) -> None:
    link = invite(app_pool, cast.alicia, cast.gina)
    wrong_gestor = call(app_pool, cast.gus, "accept_gestor_access", link)
    assert (wrong_gestor.sqlstate, wrong_gestor.message) == ("P0001", "gestor_access_not_found")
    assert call(app_pool, cast.beto, "accept_gestor_access", link).sqlstate == "42501", "un usuario no es gestor"
    assert call(app_pool, cast.alicia, "accept_gestor_access", link).sqlstate == "42501", (
        "el dueño no se acepta a sí mismo"
    )
    assert not reads_alicia(app_pool, cast, "gus")


def test_an_expired_invitation_cannot_be_accepted(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    link = invite(app_pool, cast.alicia, cast.gina)
    admin.execute("update public.gestor_access set expires_at = now() - interval '1 minute' where id = %s", (link,))
    out = call(app_pool, cast.gina, "accept_gestor_access", link)
    assert (out.sqlstate, out.message) == ("P0001", "gestor_access_expired")


def test_an_invitation_can_be_accepted_only_once(app_pool: Pool, cast: Cast) -> None:
    link = invite(app_pool, cast.alicia, cast.gina)
    assert not call(app_pool, cast.gina, "accept_gestor_access", link).error
    again = call(app_pool, cast.gina, "accept_gestor_access", link)
    assert (again.sqlstate, again.message) == ("P0001", "gestor_access_not_pending")


def test_only_the_owner_can_revoke(app_pool: Pool, cast: Cast) -> None:
    link = apply_scenario(app_pool, cast, "active")
    by_gestor = call(app_pool, cast.gina, "revoke_gestor_access", link)
    assert (by_gestor.sqlstate, by_gestor.message) == ("P0001", "not_the_owner")
    by_stranger = call(app_pool, cast.beto, "revoke_gestor_access", link)
    assert (by_stranger.sqlstate, by_stranger.message) == ("P0001", "gestor_access_not_found")
    assert reads_alicia(app_pool, cast)

    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    twice = call(app_pool, cast.alicia, "revoke_gestor_access", link)
    assert (twice.sqlstate, twice.message) == ("P0001", "gestor_access_not_open")


def test_a_pending_invitation_can_be_withdrawn_by_the_owner(app_pool: Pool, cast: Cast) -> None:
    link = invite(app_pool, cast.alicia, cast.gina)
    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert call(app_pool, cast.gina, "accept_gestor_access", link).message == "gestor_access_not_pending"


# --- Reglas de la invitación ----------------------------------------------------------------------------------------------


def test_only_the_owner_can_invite_and_only_somebody_else(app_pool: Pool, cast: Cast) -> None:
    sql = "insert into public.gestor_access (owner_id, gestor_email) values (%s, %s)"
    assert attempt(app_pool, cast.beto, sql, (cast.alicia.id, cast.gina.email)).sqlstate == "42501"
    assert attempt(app_pool, cast.alicia, sql, (cast.alicia.id, cast.alicia.email)).sqlstate == "42501"
    assert attempt(app_pool, cast.alicia, sql, (cast.alicia.id, cast.gina.email)).rowcount == 1


def test_an_invitation_cannot_be_created_already_active(app_pool: Pool, cast: Cast) -> None:
    for column, value in (("status", "active"), ("gestor_id", cast.gina.id), ("expires_at", "2999-01-01")):
        out = attempt(
            app_pool,
            cast.alicia,
            f"insert into public.gestor_access (owner_id, gestor_email, {column}) values (%s, %s, %s)",
            (cast.alicia.id, cast.gina.email, value),
        )
        assert out.sqlstate == "42501", f"Alicia pudo fijar {column} al invitar"


def test_there_is_one_open_invitation_per_gestor_and_it_can_be_repeated_after_revoking(
    app_pool: Pool, cast: Cast
) -> None:
    link = invite(app_pool, cast.alicia, cast.gina)
    duplicate = attempt(
        app_pool,
        cast.alicia,
        "insert into public.gestor_access (owner_id, gestor_email) values (%s, %s)",
        (cast.alicia.id, cast.gina.email),
    )
    assert duplicate.sqlstate == "23505"
    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert invite(app_pool, cast.alicia, cast.gina) != link


def test_the_invited_email_must_be_lowercase(app_pool: Pool, cast: Cast) -> None:
    out = attempt(
        app_pool,
        cast.alicia,
        "insert into public.gestor_access (owner_id, gestor_email) values (%s, %s)",
        (cast.alicia.id, cast.gina.email.upper()),
    )
    assert out.sqlstate == "23514"


@pytest.mark.parametrize("scenario", ["pending", "active", "revoked", "declined"])
def test_a_stranger_gestor_never_sees_the_link(app_pool: Pool, cast: Cast, scenario: str) -> None:
    apply_scenario(app_pool, cast, scenario)
    assert visible_owners(app_pool, cast.gus, "gestor_access", "owner_id") == set()
    assert visible_owners(app_pool, cast.beto, "gestor_access", "owner_id") == set()
