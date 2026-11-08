"""AC-09 a AC-13, AC-17 · La tabla `invoice_series`, su trigger y las funciones `app.*` (SPEC-W-005 §5.2, D-03, D-07).

La tabla no se escribe directamente ni el dueño; el trigger defiende la numeración venga la sentencia de donde venga (varias comprobaciones
escriben como dueño de la base de datos para demostrarlo); las funciones toman un cerrojo asesor por persona (Anexo B.1: sin él, `ensure` y
`create` predeterminada a la vez hacían fallar a una con 23505). La visibilidad por rol y por estado del vínculo la prueba la matriz de RLS.
"""

import threading
import time
import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.db import user_transaction
from cuadre.profile import year_series_code
from tests.support import Cast, Outcome, Person, Pool, apply_scenario, attempt, call

# --- Ayudas -------------------------------------------------------------------------------------------------------------------------


def rows(admin: Connection[DictRow], person: Person) -> list[dict[str, Any]]:
    return admin.execute(
        "select * from public.invoice_series where owner_id = %s order by code", (person.id,)
    ).fetchall()


def by_code(admin: Connection[DictRow], person: Person, code: str) -> dict[str, Any]:
    found = [r for r in rows(admin, person) if r["code"] == code]
    assert len(found) == 1, f"{code}: {len(found)} filas"
    return found[0]


def made(out: Outcome) -> uuid.UUID:
    assert not out.error, out.message
    return next(iter(out.rows[0].values()))


def create(
    pool: Pool,
    person: Person,
    code: str,
    description: str | None = None,
    first: int | None = None,
    default: bool = False,
) -> Outcome:
    return call(pool, person, "create_invoice_series", code, description, first, default)


def update(pool: Pool, person: Person, series_id: object, changes: object) -> Outcome:
    return call(pool, person, "update_invoice_series", series_id, Jsonb(changes) if changes is not None else None)


def code_of(out: Outcome) -> str:
    """El código estable del error (`series_in_use`…): es el mensaje de la excepción."""
    assert out.sqlstate == "P0001", (out.sqlstate, out.message)
    return (out.message or "").strip()


def use(admin: Connection[DictRow], series_id: object, issued: int = 1) -> None:
    """Simula `issued` emisiones de SPEC-W-007: avanza `next_number` como dueño de la base de datos."""
    admin.execute("update public.invoice_series set next_number = next_number + %s where id = %s", (issued, series_id))


def year(admin: Connection[DictRow]) -> str:
    row = admin.execute("select to_char(private.today_madrid(), 'YYYY') as y").fetchone()
    assert row is not None
    return str(row["y"])


def insert_direct(admin: Connection[DictRow], person: Person, **fields: Any) -> uuid.UUID:
    values = {"owner_id": person.id, "code": "DIR", **fields}
    columns = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    row = admin.execute(
        f"insert into public.invoice_series ({columns}) values ({marks}) returning id", tuple(values.values())
    ).fetchone()
    assert row is not None
    return row["id"]


# --- Quién las ve ------------------------------------------------------------------------------------------------------------------------

SCENARIOS = ["baseline", "pending", "active", "revoked", "declined"]


def sees(pool: Pool, person: Person, code: str) -> bool:
    out = attempt(pool, person, "select id from public.invoice_series where code = %s", (code,))
    assert not out.error, out.message
    return bool(out.rows)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_who_sees_alicias_series_in_each_link_state(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, scenario: str
) -> None:
    """El dueño ve las suyas (archivadas incluidas); el gestor, solo con el vínculo ACTIVO; el administrador, ninguna (D3)."""
    apply_scenario(app_pool, cast, scenario)
    insert_direct(admin, cast.alicia, code="VIS")
    insert_direct(admin, cast.alicia, code="ARC", archived_at="2026-01-01")
    insert_direct(admin, cast.beto, code="BVIS")

    expected = {"alicia": True, "beto": False, "gina": scenario == "active", "gus": False, "adan": False}
    for key, allowed in expected.items():
        assert sees(app_pool, cast[key], "VIS") is allowed, f"{scenario}: {key} y la serie de alicia"
        assert sees(app_pool, cast[key], "ARC") is allowed, f"{scenario}: {key} y la archivada de alicia"
    assert sees(app_pool, cast.beto, "BVIS") and not sees(app_pool, cast.alicia, "BVIS")
    assert not sees(app_pool, cast.gina, "BVIS"), "el gestor solo ve a quien le dio acceso"
    assert not sees(app_pool, cast.adan, "BVIS")


# --- Nadie escribe directamente ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_writes_the_table_directly_not_even_the_owner(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    sid = insert_direct(admin, cast.alicia, code="BASE")
    person = cast[who]
    inserted = attempt(
        app_pool, person, "insert into public.invoice_series (owner_id, code) values (%s, 'NOPE')", (person.id,)
    )
    assert inserted.sqlstate == "42501"
    changed = attempt(app_pool, person, "update public.invoice_series set description = 'hacked' where id = %s", (sid,))
    assert changed.sqlstate == "42501"
    removed = attempt(app_pool, person, "delete from public.invoice_series where id = %s", (sid,))
    assert removed.sqlstate == "42501"
    assert by_code(admin, cast.alicia, "BASE")["description"] is None


def test_the_table_has_forced_rls_and_only_select_for_authenticated(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select relrowsecurity as rls, relforcerowsecurity as forced from pg_class where oid = 'public.invoice_series'::regclass"
    ).fetchone()
    assert row == {"rls": True, "forced": True}
    privileges = {
        p: bool(
            admin.execute(
                "select has_table_privilege('authenticated', 'public.invoice_series', %s) as ok", (p,)
            ).fetchone()["ok"]
        )  # type: ignore[index]
        for p in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
    }
    assert privileges == {"SELECT": True, "INSERT": False, "UPDATE": False, "DELETE": False, "TRUNCATE": False}
    for role in ("anon", "service_role"):
        for p in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            ok = admin.execute(
                "select has_table_privilege(%s, 'public.invoice_series', %s) as ok", (role, p)
            ).fetchone()
            assert ok is not None and ok["ok"] is False, (role, p)


# --- Las CHECK y los índices, por nombre ----------------------------------------------------------------------------------------------------


def violation(admin: Connection[DictRow], person: Person, error: type[psycopg.Error], **fields: Any) -> str:
    with pytest.raises(error) as info:
        insert_direct(admin, person, **fields)
    return info.value.diag.constraint_name or ""


@pytest.mark.parametrize("code", ["", "a", "-A", "A-", "ABCDEFGHI", "A B", "A_B", "A\n", "--", "Ñ"])
def test_the_code_format_check(admin: Connection[DictRow], cast: Cast, code: str) -> None:
    assert violation(admin, cast.alicia, psycopg.errors.CheckViolation, code=code) == "invoice_series_code_format"


@pytest.mark.parametrize("code", ["A", "2026", "AB", "F-1", "ABCDEFGH", "A-B-C-D"])
def test_codes_the_check_accepts(admin: Connection[DictRow], cast: Cast, code: str) -> None:
    insert_direct(admin, cast.alicia, code=code)


def test_the_other_checks(admin: Connection[DictRow], cast: Cast) -> None:
    check = psycopg.errors.CheckViolation
    assert violation(admin, cast.alicia, check, description="a" * 81) == "invoice_series_description_length"
    assert violation(admin, cast.alicia, check, first_number=0, next_number=0) == "invoice_series_first_number_range"
    assert (
        violation(admin, cast.alicia, check, first_number=1_000_000, next_number=1_000_000)
        == "invoice_series_first_number_range"
    )
    assert violation(admin, cast.alicia, check, next_number=1_000_001) == "invoice_series_next_number_range"
    assert violation(admin, cast.alicia, check, first_number=10, next_number=9) == "invoice_series_next_not_below_first"
    assert (
        violation(admin, cast.alicia, check, is_default=True, archived_at="2026-01-01")
        == "invoice_series_default_not_archived"
    )


def test_the_bounds_the_checks_accept(admin: Connection[DictRow], cast: Cast) -> None:
    insert_direct(admin, cast.alicia, code="LOW", first_number=1, next_number=1, description="a" * 80)
    insert_direct(admin, cast.alicia, code="HIGH", first_number=999_999, next_number=1_000_000)


def test_a_code_is_unique_per_owner_archived_ones_included(admin: Connection[DictRow], cast: Cast) -> None:
    insert_direct(admin, cast.alicia, code="DUP", archived_at="2026-01-01")
    assert violation(admin, cast.alicia, psycopg.errors.UniqueViolation, code="DUP") == "invoice_series_owner_code_key"
    insert_direct(admin, cast.beto, code="DUP")  # el mismo código en otra persona, bien


def test_only_one_default_per_owner(admin: Connection[DictRow], cast: Cast) -> None:
    insert_direct(admin, cast.alicia, code="UNO", is_default=True)
    assert (
        violation(admin, cast.alicia, psycopg.errors.UniqueViolation, code="DOS", is_default=True)
        == "invoice_series_one_default"
    )
    insert_direct(admin, cast.alicia, code="TRES", is_default=False)
    insert_direct(admin, cast.beto, code="UNO", is_default=True)  # otra persona puede tener la suya


def test_the_series_goes_away_with_the_account_but_invoices_will_not_cascade(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select confdeltype as t from pg_constraint where conrelid = 'public.invoice_series'::regclass and contype = 'f'"
    ).fetchone()
    assert row is not None and row["t"] == "c"  # CASCADE: es configuración (las facturas de SPEC-W-007 no la usarán)


# --- El trigger, regla a regla ----------------------------------------------------------------------------------------------------------


def trigger_error(admin: Connection[DictRow], sql: str, *params: Any) -> str:
    with pytest.raises(psycopg.errors.RaiseException) as info:
        admin.execute(sql, params)
    return info.value.diag.message_primary or ""


def test_updated_at_moves_when_a_series_changes(admin: Connection[DictRow], cast: Cast) -> None:
    sid = insert_direct(admin, cast.alicia, code="TCH")
    before = by_code(admin, cast.alicia, "TCH")["updated_at"]
    admin.execute("update public.invoice_series set description = 'x' where id = %s", (sid,))
    assert by_code(admin, cast.alicia, "TCH")["updated_at"] > before


def test_identity_columns_never_change(admin: Connection[DictRow], cast: Cast) -> None:
    sid = insert_direct(admin, cast.alicia, code="IDT")
    for column, value in (("owner_id", cast.beto.id), ("id", uuid.uuid4()), ("created_at", "2000-01-01")):
        assert (
            trigger_error(admin, f"update public.invoice_series set {column} = %s where id = %s", value, sid)
            == "series_immutable_column"
        )


def test_an_unused_series_can_change_code_and_first_number_together_with_next(
    admin: Connection[DictRow], cast: Cast
) -> None:
    sid = insert_direct(admin, cast.alicia, code="OLD")
    admin.execute("update public.invoice_series set code = 'NEW' where id = %s", (sid,))
    admin.execute("update public.invoice_series set first_number = 500, next_number = 500 where id = %s", (sid,))
    admin.execute(
        "update public.invoice_series set first_number = 100, next_number = 100 where id = %s", (sid,)
    )  # bajar next con first: bien
    row = by_code(admin, cast.alicia, "NEW")
    assert (row["first_number"], row["next_number"]) == (100, 100)


def test_lowering_first_number_alone_is_refused_the_hole_of_the_first_draft(
    admin: Connection[DictRow], cast: Cast
) -> None:
    """B.1: bajar `first_number` sin tocar `next_number` dejaba la serie «en uso» sin haberse emitido nada."""
    sid = insert_direct(admin, cast.alicia, code="HOLE", first_number=100, next_number=100)
    assert (
        trigger_error(admin, "update public.invoice_series set first_number = 50 where id = %s", sid)
        == "series_first_number_mismatch"
    )
    assert by_code(admin, cast.alicia, "HOLE")["first_number"] == 100


def test_a_series_in_use_keeps_its_code_and_first_number(admin: Connection[DictRow], cast: Cast) -> None:
    sid = insert_direct(admin, cast.alicia, code="USED", first_number=5, next_number=5)
    use(admin, sid)
    assert trigger_error(admin, "update public.invoice_series set code = 'OTHER' where id = %s", sid) == "series_in_use"
    assert (
        trigger_error(admin, "update public.invoice_series set first_number = 1, next_number = 1 where id = %s", sid)
        == "series_in_use"
    )
    assert (
        trigger_error(admin, "update public.invoice_series set first_number = 1 where id = %s", sid) == "series_in_use"
    )
    admin.execute("update public.invoice_series set description = 'ok' where id = %s", (sid,))  # la descripción sí
    admin.execute("update public.invoice_series set is_default = true where id = %s", (sid,))
    admin.execute("update public.invoice_series set archived_at = null where id = %s", (sid,))


def test_next_number_never_goes_down_in_a_series_in_use(admin: Connection[DictRow], cast: Cast) -> None:
    sid = insert_direct(admin, cast.alicia, code="NEXT", first_number=1, next_number=1)
    use(admin, sid, 5)
    assert (
        trigger_error(admin, "update public.invoice_series set next_number = 5 where id = %s", sid)
        == "series_number_regression"
    )
    assert (
        trigger_error(admin, "update public.invoice_series set next_number = 1 where id = %s", sid)
        == "series_number_regression"
    )
    admin.execute("update public.invoice_series set next_number = 7 where id = %s", (sid,))  # subir, bien
    assert by_code(admin, cast.alicia, "NEXT")["next_number"] == 7


def test_next_number_only_moves_with_first_number_in_an_unused_series(admin: Connection[DictRow], cast: Cast) -> None:
    sid = insert_direct(admin, cast.alicia, code="UNU", first_number=10, next_number=10)
    # Bajar solo `next_number` por debajo de `first_number` lo frena la CHECK `next_not_below_first` o el trigger.
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.RaiseException)):
        admin.execute("update public.invoice_series set next_number = 5 where id = %s", (sid,))


# --- Las funciones: ensure_year_series -------------------------------------------------------------------------------------------------


def test_ensure_creates_the_year_series_as_the_default(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    sid = made(call(app_pool, cast.alicia, "ensure_year_series"))
    row = by_code(admin, cast.alicia, year(admin))
    assert row["id"] == sid
    assert (row["description"], row["first_number"], row["next_number"], row["is_default"], row["archived_at"]) == (
        "Serie del año",
        1,
        1,
        True,
        None,
    )


def test_ensure_is_idempotent(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    first = made(call(app_pool, cast.alicia, "ensure_year_series"))
    second = made(call(app_pool, cast.alicia, "ensure_year_series"))
    assert first == second and len(rows(admin, cast.alicia)) == 1


def test_ensure_does_not_take_the_default_away_from_another_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    made(create(app_pool, cast.alicia, "FAC", default=True))
    made(call(app_pool, cast.alicia, "ensure_year_series"))
    assert by_code(admin, cast.alicia, "FAC")["is_default"] is True
    assert by_code(admin, cast.alicia, year(admin))["is_default"] is False


def test_ensure_returns_the_existing_year_series_even_if_it_is_archived_or_used(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sid = made(call(app_pool, cast.alicia, "ensure_year_series"))
    use(admin, sid, 3)
    made(create(app_pool, cast.alicia, "FAC", default=True))
    made(call(app_pool, cast.alicia, "set_invoice_series_archived", sid, True))
    assert made(call(app_pool, cast.alicia, "ensure_year_series")) == sid
    assert by_code(admin, cast.alicia, year(admin))["next_number"] == 4


def test_the_year_series_code_is_the_domains_for_todays_date(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    made(call(app_pool, cast.alicia, "ensure_year_series"))
    today = admin.execute("select private.today_madrid() as d").fetchone()
    assert today is not None
    assert rows(admin, cast.alicia)[0]["code"] == year_series_code(today["d"])


def test_ensure_takes_the_year_from_madrid_and_not_from_the_servers_clock(admin: Connection[DictRow]) -> None:
    """`now()` no se puede fijar y el año solo difiere del de Madrid en la noche del 31 de diciembre: lo que se puede comprobar es que la función
    sigue usando `private.today_madrid()` y no `current_date`, `now()` ni `localtimestamp` (el mismo límite que SPEC-W-003 B.3)."""
    row = admin.execute("select prosrc from pg_proc where oid = 'app.ensure_year_series()'::regprocedure").fetchone()
    assert row is not None
    source = row["prosrc"]
    assert "private.today_madrid()" in source
    for clock in ("current_date", "now()", "localtimestamp", "current_timestamp"):
        assert clock not in source, clock
    today = admin.execute("select pg_get_functiondef('private.today_madrid()'::regprocedure) as d").fetchone()
    assert today is not None and "Europe/Madrid" in today["d"]


def test_each_person_gets_their_own_year_series(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    a = made(call(app_pool, cast.alicia, "ensure_year_series"))
    b = made(call(app_pool, cast.beto, "ensure_year_series"))
    assert a != b and len(rows(admin, cast.alicia)) == 1 and len(rows(admin, cast.beto)) == 1


# --- create_invoice_series ---------------------------------------------------------------------------------------------------------------


def test_create_with_defaults(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(create(app_pool, cast.alicia, "FAC"))
    row = by_code(admin, cast.alicia, "FAC")
    assert (row["description"], row["first_number"], row["next_number"], row["is_default"]) == (None, 1, 1, False)


def test_create_with_a_description_and_a_first_number(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(create(app_pool, cast.alicia, "FAC", "  Principal  ", 100))
    row = by_code(admin, cast.alicia, "FAC")
    assert (row["description"], row["first_number"], row["next_number"]) == ("Principal", 100, 100)


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_description_is_stored_as_null(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, blank: str
) -> None:
    made(create(app_pool, cast.alicia, "FAC", blank))
    assert by_code(admin, cast.alicia, "FAC")["description"] is None


def test_creating_a_default_series_takes_the_mark_from_the_previous_one(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    made(create(app_pool, cast.alicia, "UNO", default=True))
    made(create(app_pool, cast.alicia, "DOS", default=True))
    assert [(r["code"], r["is_default"]) for r in rows(admin, cast.alicia)] == [("DOS", True), ("UNO", False)]


def test_a_code_already_used_is_refused_archived_ones_too(app_pool: Pool, cast: Cast) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC"))
    assert code_of(create(app_pool, cast.alicia, "FAC")) == "series_code_taken"
    made(call(app_pool, cast.alicia, "set_invoice_series_archived", sid, True))
    assert code_of(create(app_pool, cast.alicia, "FAC")) == "series_code_taken"
    made(create(app_pool, cast.beto, "FAC"))  # otra persona, bien


@pytest.mark.parametrize("code", [None, "", "fac", "-A", "A-", "ABCDEFGHI", "A B", "ß"])
def test_create_refuses_a_bad_code_naming_the_field(app_pool: Pool, cast: Cast, code: str | None) -> None:
    out = create(app_pool, cast.alicia, code)  # type: ignore[arg-type]
    assert code_of(out) == "invalid_series" and out.detail == "code"


def test_create_refuses_a_bad_description_or_first_number_naming_the_field(app_pool: Pool, cast: Cast) -> None:
    out = create(app_pool, cast.alicia, "FAC", "a" * 81)
    assert code_of(out) == "invalid_series" and out.detail == "description"
    for number in (0, -1, 1_000_000):
        out = create(app_pool, cast.alicia, "FAC", None, number)
        assert code_of(out) == "invalid_series" and out.detail == "first_number", number


# --- update_invoice_series -------------------------------------------------------------------------------------------------------------------


def test_update_with_no_changes_does_nothing(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC", "x", 7))
    before = by_code(admin, cast.alicia, "FAC")
    assert not update(app_pool, cast.alicia, sid, {}).error
    assert by_code(admin, cast.alicia, "FAC") | {"updated_at": None} == before | {"updated_at": None}


def test_an_unused_series_changes_code_description_and_first_number(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC", "x", 7))
    assert not update(
        app_pool, cast.alicia, sid, {"code": "NEW", "description": "  Nueva  ", "first_number": 500}
    ).error
    row = by_code(admin, cast.alicia, "NEW")
    assert (row["description"], row["first_number"], row["next_number"]) == ("Nueva", 500, 500)


def test_a_description_can_be_cleared(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC", "x"))
    assert not update(app_pool, cast.alicia, sid, {"description": None}).error
    assert by_code(admin, cast.alicia, "FAC")["description"] is None
    assert not update(app_pool, cast.alicia, sid, {"description": "  "}).error
    assert by_code(admin, cast.alicia, "FAC")["description"] is None


def test_a_series_in_use_keeps_code_and_first_number_but_not_the_description(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC", "x", 10))
    use(admin, sid)
    assert code_of(update(app_pool, cast.alicia, sid, {"code": "NEW"})) == "series_in_use"
    assert code_of(update(app_pool, cast.alicia, sid, {"first_number": 1})) == "series_in_use"
    assert not update(app_pool, cast.alicia, sid, {"description": "otra"}).error
    # El mismo valor no es un cambio, ni en una serie en uso.
    assert not update(app_pool, cast.alicia, sid, {"code": "FAC", "first_number": 10}).error
    row = by_code(admin, cast.alicia, "FAC")
    assert (row["description"], row["first_number"], row["next_number"]) == ("otra", 10, 11)


def test_changing_the_code_to_one_that_exists_is_refused(app_pool: Pool, cast: Cast) -> None:
    made(create(app_pool, cast.alicia, "UNO"))
    two = made(create(app_pool, cast.alicia, "DOS"))
    assert code_of(update(app_pool, cast.alicia, two, {"code": "UNO"})) == "series_code_taken"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"code": "fac"}, "code"),
        ({"code": 5}, "code"),
        ({"code": None}, "code"),
        ({"code": "ABCDEFGHI"}, "code"),
        ({"description": 5}, "description"),
        ({"description": "a" * 81}, "description"),
        ({"first_number": 0}, "first_number"),
        ({"first_number": 1_000_000}, "first_number"),
        ({"first_number": "5"}, "first_number"),
        ({"first_number": 5.5}, "first_number"),
        ({"first_number": None}, "first_number"),
        ({"first_number": -3}, "first_number"),
        ({"first_number": 12345678}, "first_number"),
        ({"is_default": True}, "changes"),
        ({"archived": True}, "changes"),
        ({"owner_id": "x"}, "changes"),
    ],
)
def test_update_refuses_bad_changes_naming_the_field(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, changes: dict[str, Any], field: str
) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC", "x", 7))
    out = update(app_pool, cast.alicia, sid, changes)
    assert code_of(out) == "invalid_series" and out.detail == field
    assert by_code(admin, cast.alicia, "FAC")["first_number"] == 7


@pytest.mark.parametrize("changes", [[], "texto", 5, None])
def test_update_needs_an_object(app_pool: Pool, cast: Cast, changes: object) -> None:
    sid = made(create(app_pool, cast.alicia, "FAC"))
    out = update(app_pool, cast.alicia, sid, changes)
    assert code_of(out) == "invalid_series" and out.detail == "changes"


# --- set_default_invoice_series y archivar ---------------------------------------------------------------------------------------------------


def test_setting_the_default_moves_the_mark(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(create(app_pool, cast.alicia, "UNO", default=True))
    two = made(create(app_pool, cast.alicia, "DOS"))
    assert not call(app_pool, cast.alicia, "set_default_invoice_series", two).error
    assert [(r["code"], r["is_default"]) for r in rows(admin, cast.alicia)] == [("DOS", True), ("UNO", False)]
    assert not call(app_pool, cast.alicia, "set_default_invoice_series", two).error  # ya lo era: no hace nada
    assert sum(r["is_default"] for r in rows(admin, cast.alicia)) == 1


def test_an_archived_series_cannot_be_the_default(app_pool: Pool, cast: Cast) -> None:
    made(create(app_pool, cast.alicia, "UNO", default=True))
    two = made(create(app_pool, cast.alicia, "DOS"))
    made(call(app_pool, cast.alicia, "set_invoice_series_archived", two, True))
    assert code_of(call(app_pool, cast.alicia, "set_default_invoice_series", two)) == "series_archived"


def test_archiving_and_reactivating(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(create(app_pool, cast.alicia, "UNO", default=True))
    two = made(create(app_pool, cast.alicia, "DOS"))
    use(admin, two, 4)  # archivar vale también con facturas emitidas
    assert not call(app_pool, cast.alicia, "set_invoice_series_archived", two, True).error
    first_time = by_code(admin, cast.alicia, "DOS")["archived_at"]
    assert first_time is not None
    assert not call(
        app_pool, cast.alicia, "set_invoice_series_archived", two, True
    ).error  # repetirlo no cambia la fecha
    assert by_code(admin, cast.alicia, "DOS")["archived_at"] == first_time
    assert not call(app_pool, cast.alicia, "set_invoice_series_archived", two, False).error
    row = by_code(admin, cast.alicia, "DOS")
    assert row["archived_at"] is None and row["next_number"] == 5


def test_the_default_cannot_be_archived_and_the_error_is_ours_not_the_checks(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sid = made(create(app_pool, cast.alicia, "UNO", default=True))
    out = call(app_pool, cast.alicia, "set_invoice_series_archived", sid, True)
    assert code_of(out) == "series_is_default"  # P0001 con nuestro código, no un 23514 de la CHECK
    assert by_code(admin, cast.alicia, "UNO")["archived_at"] is None


def test_archiving_needs_a_boolean(app_pool: Pool, cast: Cast) -> None:
    sid = made(create(app_pool, cast.alicia, "UNO"))
    out = call(app_pool, cast.alicia, "set_invoice_series_archived", sid, None)
    assert code_of(out) == "invalid_series" and out.detail == "archived"


# --- Roles y ajenas -------------------------------------------------------------------------------------------------------------------------

CALLS = [
    ("ensure_year_series", ()),
    ("create_invoice_series", ("FAC", None, None, False)),
    ("set_default_invoice_series", (uuid.uuid4(),)),
    ("set_invoice_series_archived", (uuid.uuid4(), True)),
    ("update_invoice_series", (uuid.uuid4(), Jsonb({}))),
    ("set_business_logo", ("x",)),
    ("clear_business_logo", ()),
]


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
@pytest.mark.parametrize(("function", "args"), CALLS)
def test_only_a_usuario_can_call_the_functions(
    app_pool: Pool, cast: Cast, who: str, function: str, args: tuple[Any, ...]
) -> None:
    assert call(app_pool, cast[who], function, *args).sqlstate == "42501"


@pytest.mark.parametrize(
    "function", ["set_default_invoice_series", "set_invoice_series_archived", "update_invoice_series"]
)
def test_anothers_series_looks_like_one_that_does_not_exist(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, function: str
) -> None:
    mine = made(create(app_pool, cast.alicia, "MINE"))
    args = {
        "set_default_invoice_series": (mine,),
        "set_invoice_series_archived": (mine, True),
        "update_invoice_series": (mine, Jsonb({"description": "hacked"})),
    }[function]
    foreign = call(app_pool, cast.beto, function, *args)
    missing = call(app_pool, cast.beto, function, uuid.uuid4(), *args[1:])
    assert code_of(foreign) == code_of(missing) == "series_not_found"
    assert by_code(admin, cast.alicia, "MINE")["description"] is None


def test_a_suspended_account_changes_nothing(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert call(app_pool, cast.alicia, "ensure_year_series").sqlstate == "42501"
    assert create(app_pool, cast.alicia, "FAC").sqlstate == "42501"


def test_the_functions_write_nothing_to_the_activity_log(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    def count() -> int:
        row = admin.execute(
            "select count(*) as n from public.activity_log where owner_id = %s", (cast.alicia.id,)
        ).fetchone()
        assert row is not None
        return int(row["n"])

    before = count()
    sid = made(call(app_pool, cast.alicia, "ensure_year_series"))
    other = made(create(app_pool, cast.alicia, "FAC", default=True))
    update(app_pool, cast.alicia, other, {"description": "x"})
    call(app_pool, cast.alicia, "set_default_invoice_series", sid)
    call(app_pool, cast.alicia, "set_invoice_series_archived", other, True)
    assert count() == before


# --- Concurrencia: el cerrojo por persona ---------------------------------------------------------------------------------------------------------


def run_while_holding(
    pool: Pool,
    person: Person,
    hold: str,
    hold_args: tuple[Any, ...],
    then: str,
    then_args: tuple[Any, ...],
    other: Person | None = None,
) -> tuple[bool, Outcome]:
    """Ejecuta `hold` sin confirmar y, desde otro hilo, `then`. Devuelve (¿esperó?, resultado del segundo)."""
    outcome: dict[str, Outcome] = {}
    waiter = threading.Thread(target=lambda: outcome.update(second=call(pool, other or person, then, *then_args)))
    with user_transaction(pool, person.id) as conn:
        marks = ", ".join(["%s"] * len(hold_args))
        conn.execute(f"select app.{hold}({marks})", hold_args)  # aún sin confirmar
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=15)
    assert not waiter.is_alive(), "el segundo hilo no terminó"
    return still_waiting, outcome["second"]


def test_ensure_and_create_a_default_series_at_the_same_time_leave_one_default_and_no_error(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """B.1: sin cerrojo, la segunda fallaba con 23505 en el índice de la predeterminada. Con él espera y ve lo que hizo la primera."""
    waited, second = run_while_holding(
        app_pool, cast.alicia, "ensure_year_series", (), "create_invoice_series", ("FAC", None, None, True)
    )
    assert waited, "la segunda operación no esperó a la primera"
    assert not second.error, second.message
    found = rows(admin, cast.alicia)
    assert sorted(r["code"] for r in found) == sorted([year(admin), "FAC"])
    assert [r["code"] for r in found if r["is_default"]] == ["FAC"]


def test_two_ensures_at_the_same_time_leave_one_row(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    waited, second = run_while_holding(app_pool, cast.alicia, "ensure_year_series", (), "ensure_year_series", ())
    assert waited and not second.error
    assert len(rows(admin, cast.alicia)) == 1 and rows(admin, cast.alicia)[0]["is_default"] is True


def test_two_creations_of_the_same_code_give_our_error_not_a_unique_violation(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        "create_invoice_series",
        ("FAC", None, None, False),
        "create_invoice_series",
        ("FAC", None, None, False),
    )
    assert waited
    assert code_of(second) == "series_code_taken"
    assert len(rows(admin, cast.alicia)) == 1


def test_two_default_changes_at_the_same_time_leave_one_default(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    one = made(create(app_pool, cast.alicia, "UNO", default=True))
    two = made(create(app_pool, cast.alicia, "DOS"))
    waited, second = run_while_holding(
        app_pool, cast.alicia, "set_default_invoice_series", (two,), "set_default_invoice_series", (one,)
    )
    assert waited and not second.error
    assert [r["code"] for r in rows(admin, cast.alicia) if r["is_default"]] == ["UNO"]


def test_the_lock_is_per_person_not_global(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """Mientras Alicia tiene el cerrojo, Beto no espera."""
    waited, second = run_while_holding(
        app_pool, cast.alicia, "ensure_year_series", (), "ensure_year_series", (), other=cast.beto
    )
    assert not waited, "Beto esperó a Alicia"
    assert not second.error
    assert len(rows(admin, cast.beto)) == 1


def test_the_lock_is_taken_even_by_the_functions_that_do_not_create(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sid = made(create(app_pool, cast.alicia, "UNO"))
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        "set_invoice_series_archived",
        (sid, True),
        "update_invoice_series",
        (sid, Jsonb({"description": "x"})),
    )
    assert waited and not second.error
    row = by_code(admin, cast.alicia, "UNO")
    assert row["description"] == "x" and row["archived_at"] is not None
