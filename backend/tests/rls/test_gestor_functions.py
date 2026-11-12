"""SPEC-W-010 hito 1 · Las funciones del acceso del gestor en la base de datos: invitar, invitaciones recibidas, registrar lecturas y anotaciones.

Se prueban como las ejecutaría la API (`user_transaction` con la identidad de cada persona del reparto) y se comprueba con privilegios de administrador lo que
queda en `activity_log` y en `gestor_notes`: solo ids, nunca texto de la anotación ni datos financieros.
"""

import uuid
from datetime import date
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.rls.expenses_support import insert, manual
from tests.rls.invoices_support import code_of, issue, made, ready
from tests.support import Cast, Person, Pool, apply_scenario, attempt, call, invite, make_cast, new_document


def log_of(admin: Connection[DictRow], owner: Person) -> list[dict[str, Any]]:
    return admin.execute(
        "select action, actor_id, actor_role::text as actor_role, entity_type, entity_id, metadata "
        "from public.activity_log where owner_id = %s and category = 'access' order by id",
        (owner.id,),
    ).fetchall()


def actions(admin: Connection[DictRow], owner: Person) -> list[str]:
    return [row["action"] for row in log_of(admin, owner)]


def open_count(admin: Connection[DictRow], owner: Person) -> int:
    row = admin.execute(
        "select count(*) as n from public.gestor_access where owner_id = %s and status in ('pending', 'active')",
        (owner.id,),
    ).fetchone()
    assert row is not None
    return int(row["n"])


# --- app.invite_gestor_access -------------------------------------------------------------------------------------------------


def test_inviting_creates_a_pending_invitation_in_lowercase_and_logs_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    out = call(app_pool, cast.alicia, "invite_gestor_access", f"  {cast.gina.email.upper()}  ")
    link = made(out)
    row = admin.execute(
        "select owner_id, gestor_email, status::text as status, gestor_id, expires_at - invited_at as ttl "
        "from public.gestor_access where id = %s",
        (link,),
    ).fetchone()
    assert row is not None
    assert (row["owner_id"], row["gestor_email"], row["status"], row["gestor_id"]) == (
        cast.alicia.id,
        cast.gina.email,
        "pending",
        None,
    )
    assert row["ttl"].days == 14
    assert actions(admin, cast.alicia) == ["gestor_access.invited"]
    entry = log_of(admin, cast.alicia)[0]
    assert (entry["actor_id"], entry["actor_role"], entry["entity_type"], entry["entity_id"], entry["metadata"]) == (
        cast.alicia.id, "usuario", "gestor_access", str(link), {},
    )  # fmt: skip


def test_an_invited_gestor_can_accept_and_the_whole_trail_is_in_the_log(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    link = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    assert not call(app_pool, cast.gina, "accept_gestor_access", link).error
    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert actions(admin, cast.alicia) == ["gestor_access.invited", "gestor_access.accepted", "gestor_access.revoked"]


@pytest.mark.parametrize(
    "bad", ["", "   ", "sin-arroba", "a@b", "a b@c.de", "@c.de", "a@@c.de", "a@c.", "x" * 250 + "@c.de", None]
)
def test_a_malformed_email_is_invalid_email(app_pool: Pool, cast: Cast, bad: str | None) -> None:
    out = call(app_pool, cast.alicia, "invite_gestor_access", bad)
    assert code_of(out) == "invalid_email"


def test_nobody_invites_themselves_whatever_the_case(app_pool: Pool, cast: Cast) -> None:
    out = call(app_pool, cast.alicia, "invite_gestor_access", cast.alicia.email.upper())
    assert code_of(out) == "cannot_invite_self"


def test_an_open_invitation_cannot_be_repeated_but_a_closed_one_can(app_pool: Pool, cast: Cast) -> None:
    first = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    assert (
        code_of(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email.upper()))
        == "gestor_access_already_open"
    )
    assert not call(app_pool, cast.alicia, "revoke_gestor_access", first).error
    again = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    assert again != first


def test_an_active_link_blocks_a_second_invitation_to_the_same_gestor(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    assert code_of(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email)) == "gestor_access_already_open"


def test_an_expired_pending_invitation_is_retired_and_the_gestor_can_be_invited_again(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    old = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    admin.execute("update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (old,))
    fresh = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    assert fresh != old
    row = admin.execute(
        "select status::text as status, revoked_at from public.gestor_access where id = %s", (old,)
    ).fetchone()
    assert row is not None and row["status"] == "revoked" and row["revoked_at"] is not None


def test_the_limit_is_five_open_invitations_and_expired_ones_do_not_count(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    ids = [
        made(call(app_pool, cast.alicia, "invite_gestor_access", f"gestor{n}.{cast.alicia.email}")) for n in range(5)
    ]
    assert open_count(admin, cast.alicia) == 5
    assert (
        code_of(call(app_pool, cast.alicia, "invite_gestor_access", f"gestor9.{cast.alicia.email}"))
        == "too_many_open_invitations"
    )
    admin.execute("update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (ids[0],))
    assert made(
        call(app_pool, cast.alicia, "invite_gestor_access", f"gestor9.{cast.alicia.email}")
    )  # la caducada ya no cuenta
    assert (
        code_of(call(app_pool, cast.alicia, "invite_gestor_access", f"gestor8.{cast.alicia.email}"))
        == "too_many_open_invitations"
    )


def test_the_limit_is_per_person(app_pool: Pool, cast: Cast) -> None:
    for n in range(5):
        made(call(app_pool, cast.alicia, "invite_gestor_access", f"g{n}.{cast.alicia.email}"))
    assert made(
        call(app_pool, cast.beto, "invite_gestor_access", f"g0.{cast.alicia.email}")
    )  # otra persona, su propio límite


def test_two_invitations_at_once_never_pass_the_limit(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    from concurrent.futures import ThreadPoolExecutor

    for n in range(4):
        made(call(app_pool, cast.alicia, "invite_gestor_access", f"g{n}.{cast.alicia.email}"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(
                lambda n: call(app_pool, cast.alicia, "invite_gestor_access", f"race{n}.{cast.alicia.email}"), range(3)
            )
        )
    assert sum(1 for r in results if not r.error) == 1
    assert sorted(r.message for r in results if r.error) == ["too_many_open_invitations"] * 2
    assert open_count(admin, cast.alicia) == 5


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_only_a_usuario_invites(app_pool: Pool, cast: Cast, who: str) -> None:
    out = call(app_pool, cast[who], "invite_gestor_access", "otra@example.test")
    assert out.sqlstate == "42501"


def test_a_suspended_usuario_cannot_invite(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert call(app_pool, cast.alicia, "invite_gestor_access", "otra@example.test").sqlstate == "42501"


# --- app.list_gestor_invitations ----------------------------------------------------------------------------------------------


def test_a_gestor_lists_only_pending_unexpired_invitations_addressed_to_them(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    mine = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gus.email))  # de otro gestor
    rows = attempt(app_pool, cast.gina, "select * from app.list_gestor_invitations()").rows
    assert [row["id"] for row in rows] == [mine]
    assert rows[0]["owner_name"] == "Alicia" and rows[0]["expires_at"] > rows[0]["invited_at"]

    admin.execute("update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (mine,))
    assert attempt(app_pool, cast.gina, "select * from app.list_gestor_invitations()").rows == []


def test_an_answered_invitation_leaves_the_list(app_pool: Pool, cast: Cast) -> None:
    link = made(call(app_pool, cast.alicia, "invite_gestor_access", cast.gina.email))
    assert not call(app_pool, cast.gina, "decline_gestor_access", link).error
    assert attempt(app_pool, cast.gina, "select * from app.list_gestor_invitations()").rows == []


@pytest.mark.parametrize("who", ["alicia", "adan"])
def test_only_a_gestor_lists_invitations(app_pool: Pool, cast: Cast, who: str) -> None:
    assert attempt(app_pool, cast[who], "select * from app.list_gestor_invitations()").sqlstate == "42501"


# --- app.log_gestor_read ------------------------------------------------------------------------------------------------------


def test_a_gestor_with_an_active_link_logs_a_read_with_only_ids(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    apply_scenario(app_pool, cast, "active")
    out = call(
        app_pool, cast.gina, "log_gestor_read", cast.alicia.id, "modelo_130", None, '{"year": 2025, "quarter": 2}'
    )
    assert not out.error, out.message
    entry = log_of(admin, cast.alicia)[-1]
    assert entry["action"] == "gestor.read"
    assert (entry["actor_id"], entry["actor_role"], entry["entity_type"], entry["entity_id"]) == (
        cast.gina.id,
        "gestor",
        "modelo_130",
        None,
    )
    assert entry["metadata"] == {"year": 2025, "quarter": 2}


@pytest.mark.parametrize(
    "entity_type",
    [
        "portfolio",
        "invoices",
        "invoice",
        "invoice_pdf",
        "expenses",
        "documents",
        "document_original",
        "profile",
        "clients",
        "modelo_303",
        "modelo_130",
        "notes",
    ],
)
def test_every_read_type_of_the_spec_is_accepted(app_pool: Pool, cast: Cast, entity_type: str) -> None:
    apply_scenario(app_pool, cast, "active")
    assert not call(app_pool, cast.gina, "log_gestor_read", cast.alicia.id, entity_type, str(uuid.uuid4())).error


@pytest.mark.parametrize("scenario", ["baseline", "pending", "declined", "revoked"])
def test_no_read_is_logged_without_an_active_link(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, scenario: str
) -> None:
    apply_scenario(app_pool, cast, scenario)
    before = len(log_of(admin, cast.alicia))
    assert call(app_pool, cast.gina, "log_gestor_read", cast.alicia.id, "invoices", None).sqlstate == "42501"
    assert len(log_of(admin, cast.alicia)) == before


def test_another_gestor_a_usuario_and_the_admin_cannot_log_a_read(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    for who in ("gus", "alicia", "beto", "adan"):
        assert call(app_pool, cast[who], "log_gestor_read", cast.alicia.id, "invoices", None).sqlstate == "42501", who


@pytest.mark.parametrize(
    ("entity_type", "entity_id", "metadata", "detail"),
    [
        ("unknown", None, None, "entity_type"),
        (None, None, None, "entity_type"),
        ("invoices", "x" * 65, None, "entity_id"),
        ("modelo_303", None, '{"year": "2025"}', "metadata"),
        ("modelo_303", None, '{"importe": 1}', "metadata"),
        ("modelo_303", None, "[1]", "metadata"),
    ],
)
def test_a_read_that_would_carry_something_else_is_refused(
    app_pool: Pool, cast: Cast, entity_type: str | None, entity_id: str | None, metadata: str | None, detail: str
) -> None:
    apply_scenario(app_pool, cast, "active")
    out = call(app_pool, cast.gina, "log_gestor_read", cast.alicia.id, entity_type, entity_id, metadata)
    assert code_of(out) == "invalid_read" and out.detail == detail


def test_authenticated_cannot_write_the_log_any_other_way(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    sql = "insert into public.activity_log (category, action) values ('access', 'gestor.read')"
    assert attempt(app_pool, cast.gina, sql).error
    assert attempt(
        app_pool, cast.gina, "select private.log_activity('access', null, null, null, 'x', null, null, '{}')"
    ).error


# --- app.add_gestor_note ------------------------------------------------------------------------------------------------------


def note(
    pool: Pool,
    gestor: Person,
    owner: Person,
    body: object = "Revisa el IVA de marzo",
    kind: str | None = None,
    entity: object = None,
):
    return call(pool, gestor, "add_gestor_note", owner.id, body, kind, entity)


def test_a_gestor_with_an_active_link_adds_a_note_and_only_its_id_is_logged(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    apply_scenario(app_pool, cast, "active")
    note_id = made(note(app_pool, cast.gina, cast.alicia, "  Falta el justificante de la factura de marzo  "))
    row = admin.execute(
        "select owner_id, gestor_id, body, entity_type, entity_id from public.gestor_notes where id = %s", (note_id,)
    ).fetchone()
    assert row == {
        "owner_id": cast.alicia.id, "gestor_id": cast.gina.id, "body": "Falta el justificante de la factura de marzo",
        "entity_type": None, "entity_id": None,
    }  # fmt: skip
    entry = log_of(admin, cast.alicia)[-1]
    assert (entry["action"], entry["entity_type"], entry["entity_id"], entry["metadata"]) == (
        "gestor.note_added",
        "gestor_note",
        str(note_id),
        {},
    )
    assert "justificante" not in str(log_of(admin, cast.alicia))  # el texto de la anotación no va al registro


def test_both_sides_read_the_note_and_nobody_else(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    note_id = made(note(app_pool, cast.gina, cast.alicia))
    for who, sees in (("alicia", True), ("gina", True), ("beto", False), ("gus", False), ("adan", False)):
        rows = attempt(app_pool, cast[who], "select id from public.gestor_notes").rows
        assert (note_id in {r["id"] for r in rows}) is sees, who


def test_after_revoking_the_gestor_neither_reads_nor_adds_but_the_owner_keeps_the_notes(
    app_pool: Pool, cast: Cast
) -> None:
    link = apply_scenario(app_pool, cast, "active")
    note_id = made(note(app_pool, cast.gina, cast.alicia))
    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert attempt(app_pool, cast.gina, "select id from public.gestor_notes").rows == []
    assert note(app_pool, cast.gina, cast.alicia).sqlstate == "42501"
    assert [r["id"] for r in attempt(app_pool, cast.alicia, "select id from public.gestor_notes").rows] == [note_id]


@pytest.mark.parametrize("scenario", ["baseline", "pending", "declined", "revoked"])
def test_no_note_without_an_active_link(app_pool: Pool, cast: Cast, scenario: str) -> None:
    apply_scenario(app_pool, cast, scenario)
    assert note(app_pool, cast.gina, cast.alicia).sqlstate == "42501"


def test_another_gestor_a_usuario_and_the_admin_cannot_add_a_note(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    for who in ("gus", "alicia", "beto", "adan"):
        assert note(app_pool, cast[who], cast.alicia).sqlstate == "42501", who


@pytest.mark.parametrize("body", ["", "   ", None])
def test_an_empty_note_is_refused(app_pool: Pool, cast: Cast, body: str | None) -> None:
    apply_scenario(app_pool, cast, "active")
    out = note(app_pool, cast.gina, cast.alicia, body)
    assert code_of(out) == "invalid_note" and out.detail == "body"


def test_the_note_length_is_one_to_two_thousand_characters(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    assert made(note(app_pool, cast.gina, cast.alicia, "x"))
    assert made(note(app_pool, cast.gina, cast.alicia, "y" * 2000))
    out = note(app_pool, cast.gina, cast.alicia, "z" * 2001)
    assert code_of(out) == "invalid_note" and out.detail == "body"


def test_a_note_can_point_to_an_expense_a_document_and_an_invoice_of_that_person_only(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    apply_scenario(app_pool, cast, "active")
    expense = insert(admin, manual(cast.alicia, date=date(2026, 3, 3), name="Gasto anotado", base=1_000, total=1_000))
    document = new_document(app_pool, cast.alicia).id
    r = ready(admin, cast.alicia)
    invoice = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, base=100_000))
    for kind, entity in (("expense", expense), ("document", document), ("invoice", invoice)):
        assert made(note(app_pool, cast.gina, cast.alicia, "Mira esto", kind, entity)), kind

    other = make_cast(admin)
    foreign = insert(admin, manual(other.alicia, date=date(2026, 3, 3), name="Gasto ajeno", base=1_000, total=1_000))
    out = note(app_pool, cast.gina, cast.alicia, "Mira esto", "expense", foreign)
    assert code_of(out) == "invalid_note" and out.detail == "entity"
    assert code_of(note(app_pool, cast.gina, cast.alicia, "Mira esto", "expense", uuid.uuid4())) == "invalid_note"


@pytest.mark.parametrize(("kind", "entity_given"), [("expense", False), (None, True), ("client", True)])
def test_the_entity_comes_as_a_pair_and_from_the_known_types(
    app_pool: Pool, cast: Cast, kind: str | None, entity_given: bool
) -> None:
    apply_scenario(app_pool, cast, "active")
    out = note(app_pool, cast.gina, cast.alicia, "Hola", kind, uuid.uuid4() if entity_given else None)
    assert code_of(out) == "invalid_note" and out.detail == "entity"


def test_notes_are_append_only_even_for_the_database_owner(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    apply_scenario(app_pool, cast, "active")
    note_id = made(note(app_pool, cast.gina, cast.alicia))
    for sql in (
        "update public.gestor_notes set body = 'cambiada' where id = %s",
        "delete from public.gestor_notes where id = %s",
    ):
        with pytest.raises(Exception, match="gestor_notes_is_append_only"):
            admin.execute(sql, (note_id,))
    with pytest.raises(Exception, match="gestor_notes_is_append_only"):
        admin.execute("truncate public.gestor_notes")


def test_the_rows_cannot_be_written_directly_by_authenticated(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    sql = "insert into public.gestor_notes (owner_id, gestor_id, body) values (%s, %s, 'directa')"
    for who in ("alicia", "gina", "adan"):
        assert attempt(app_pool, cast[who], sql, (cast.alicia.id, cast.gina.id)).error, who


def test_invite_still_works_through_the_old_direct_insert_for_the_w001_tests(app_pool: Pool, cast: Cast) -> None:
    """La política de inserción directa de SPEC-W-001 se mantiene (sus pruebas la usan); la API usa solo `app.invite_gestor_access`."""
    assert invite(app_pool, cast.alicia, cast.gina)
