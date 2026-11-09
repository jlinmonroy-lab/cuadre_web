"""AC-08 a AC-13 · La tabla `clients`, su trigger y las funciones `app.*` (SPEC-W-006 §5.2, D-06 a D-09, Anexo B.1-C).

La tabla no se escribe directamente ni el dueño; el trigger defiende la identidad venga la sentencia de donde venga (varias comprobaciones
escriben como dueño de la base de datos para demostrarlo); las funciones toman un cerrojo asesor por persona (B.1-C: sin él, dos altas a la
vez con el mismo NIF hacían fallar a una con 23505 en el índice) y comprueban `client_tax_id_taken` ANTES de escribir, también al reactivar.
La visibilidad por rol y por estado del vínculo la prueba además la matriz de RLS.
"""

import threading
import time
import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from tests.support import Cast, Outcome, Person, Pool, apply_scenario, attempt, call

NIF = "B00000018"
BASE: dict[str, Any] = {
    "name": "Estudio Norte S.L.",
    "kind": "business",
    "country": "ES",
    "scope": "national",
    "tax_id": NIF,
    "address": "Calle Inventada 4, Madrid",
    "vies_status": "not_applicable",
}
EU = {
    "name": "Kreativ GmbH",
    "kind": "business",
    "country": "DE",
    "scope": "eu",
    "tax_id": "DE446120774",
    "vies_status": "valid_simulated",
}
FIELDS = ("name", "kind", "country", "scope", "tax_id", "address", "vies_status")

# --- Ayudas -------------------------------------------------------------------------------------------------------------------------


def rows(admin: Connection[DictRow], person: Person) -> list[dict[str, Any]]:
    return admin.execute("select * from public.clients where owner_id = %s order by name, id", (person.id,)).fetchall()


def by_name(admin: Connection[DictRow], person: Person, name: str) -> dict[str, Any]:
    found = [r for r in rows(admin, person) if r["name"] == name]
    assert len(found) == 1, f"{name}: {len(found)} filas"
    return found[0]


def made(out: Outcome) -> uuid.UUID:
    assert not out.error, out.message
    return next(iter(out.rows[0].values()))


def code_of(out: Outcome) -> str:
    """El código estable del error (`client_not_found`…): es el mensaje de la excepción."""
    assert out.sqlstate == "P0001", (out.sqlstate, out.message)
    return (out.message or "").strip()


def args_of(**over: Any) -> tuple[Any, ...]:
    values = {**BASE, **over}
    return tuple(values[f] for f in FIELDS)


def create(pool: Pool, person: Person, **over: Any) -> Outcome:
    return call(pool, person, "create_client", *args_of(**over))


def update(pool: Pool, person: Person, client_id: object, **over: Any) -> Outcome:
    return call(pool, person, "update_client", client_id, *args_of(**over))


def archive(pool: Pool, person: Person, client_id: object, flag: bool | None) -> Outcome:
    return call(pool, person, "set_client_archived", client_id, flag)


def insert_direct(admin: Connection[DictRow], person: Person, **fields: Any) -> uuid.UUID:
    values: dict[str, Any] = {
        "owner_id": person.id,
        "name": "Directo S.L.",
        "kind": "business",
        "country": "ES",
        "scope": "national",
        **fields,
    }
    columns = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    row = admin.execute(
        f"insert into public.clients ({columns}) values ({marks}) returning id", tuple(values.values())
    ).fetchone()
    assert row is not None
    return row["id"]


# --- Quién los ve -----------------------------------------------------------------------------------------------------------------------

SCENARIOS = ["baseline", "pending", "active", "revoked", "declined"]


def sees(pool: Pool, person: Person, name: str) -> bool:
    out = attempt(pool, person, "select id from public.clients where name = %s", (name,))
    assert not out.error, out.message
    return bool(out.rows)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_who_sees_alicias_clients_in_each_link_state(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, scenario: str
) -> None:
    """El dueño ve los suyos (archivados incluidos); el gestor, solo con el vínculo ACTIVO; el administrador, ninguno (D3)."""
    apply_scenario(app_pool, cast, scenario)
    insert_direct(admin, cast.alicia, name="Visible S.L.")
    insert_direct(admin, cast.alicia, name="Archivado S.L.", archived_at="2026-01-01")
    insert_direct(admin, cast.beto, name="De Beto S.L.")

    expected = {"alicia": True, "beto": False, "gina": scenario == "active", "gus": False, "adan": False}
    for key, allowed in expected.items():
        assert sees(app_pool, cast[key], "Visible S.L.") is allowed, f"{scenario}: {key} y el cliente de alicia"
        assert sees(app_pool, cast[key], "Archivado S.L.") is allowed, f"{scenario}: {key} y el archivado de alicia"
    assert sees(app_pool, cast.beto, "De Beto S.L.") and not sees(app_pool, cast.alicia, "De Beto S.L.")
    assert not sees(app_pool, cast.gina, "De Beto S.L."), "el gestor solo ve a quien le dio acceso"
    assert not sees(app_pool, cast.adan, "De Beto S.L.")


# --- Nadie escribe directamente ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_writes_the_table_directly_not_even_the_owner(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    cid = insert_direct(admin, cast.alicia, name="Base S.L.")
    person = cast[who]
    inserted = attempt(
        app_pool,
        person,
        "insert into public.clients (owner_id, name, kind, country, scope) values (%s, 'Nope S.L.', 'business', 'ES', 'national')",
        (person.id,),
    )
    assert inserted.sqlstate == "42501"
    assert (
        attempt(app_pool, person, "update public.clients set name = 'hacked' where id = %s", (cid,)).sqlstate == "42501"
    )
    assert attempt(app_pool, person, "delete from public.clients where id = %s", (cid,)).sqlstate == "42501"
    assert by_name(admin, cast.alicia, "Base S.L.")["address"] is None


def test_the_table_has_forced_rls_and_only_select_for_authenticated(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select relrowsecurity as rls, relforcerowsecurity as forced from pg_class where oid = 'public.clients'::regclass"
    ).fetchone()
    assert row == {"rls": True, "forced": True}
    for p, expected in (("SELECT", True), ("INSERT", False), ("UPDATE", False), ("DELETE", False), ("TRUNCATE", False)):
        found = admin.execute(
            "select has_table_privilege('authenticated', 'public.clients', %s) as ok", (p,)
        ).fetchone()
        assert found is not None and found["ok"] is expected, p
    for role in ("anon", "service_role"):
        for p in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            found = admin.execute("select has_table_privilege(%s, 'public.clients', %s) as ok", (role, p)).fetchone()
            assert found is not None and found["ok"] is False, (role, p)


def test_there_are_exactly_two_read_policies_and_none_for_the_admin(admin: Connection[DictRow]) -> None:
    found = admin.execute(
        "select policyname, cmd from pg_policies where schemaname = 'public' and tablename = 'clients' order by 1"
    ).fetchall()
    assert [(r["policyname"], r["cmd"]) for r in found] == [
        ("clients_select_gestor", "SELECT"),
        ("clients_select_owner", "SELECT"),
    ]


# --- Las CHECK y los índices, por nombre ------------------------------------------------------------------------------------------------


def violation(admin: Connection[DictRow], person: Person, error: type[psycopg.Error], **fields: Any) -> str:
    with pytest.raises(error) as info:
        insert_direct(admin, person, **fields)
    return info.value.diag.constraint_name or ""


CHECK = psycopg.errors.CheckViolation


@pytest.mark.parametrize("name", ["", "A", "a" * 201])
def test_the_name_length_check(admin: Connection[DictRow], cast: Cast, name: str) -> None:
    assert violation(admin, cast.alicia, CHECK, name=name) == "clients_name_length"


@pytest.mark.parametrize("name", ["Ab", "a" * 200])
def test_names_the_check_accepts(admin: Connection[DictRow], cast: Cast, name: str) -> None:
    insert_direct(admin, cast.alicia, name=name)


@pytest.mark.parametrize("country", ["", "E", "es", "ESP", "E1", "1E", "E ", "Ñ"])
def test_the_country_format_check(admin: Connection[DictRow], cast: Cast, country: str) -> None:
    with pytest.raises(psycopg.Error) as info:
        insert_direct(admin, cast.alicia, country=country, scope="non_eu")
    assert info.value.diag.constraint_name == "clients_country_format"


@pytest.mark.parametrize(("scope", "country"), [("national", "DE"), ("eu", "ES"), ("non_eu", "ES"), ("national", "MX")])
def test_the_scope_must_be_national_exactly_for_spain(
    admin: Connection[DictRow], cast: Cast, scope: str, country: str
) -> None:
    assert violation(admin, cast.alicia, CHECK, scope=scope, country=country) == "clients_scope_matches_country"


@pytest.mark.parametrize(("scope", "country"), [("national", "ES"), ("eu", "DE"), ("non_eu", "MX"), ("non_eu", "GB")])
def test_scopes_the_check_accepts(admin: Connection[DictRow], cast: Cast, scope: str, country: str) -> None:
    insert_direct(admin, cast.alicia, scope=scope, country=country)


def test_the_database_does_not_know_which_countries_are_in_the_eu(admin: Connection[DictRow], cast: Cast) -> None:
    """D-10: eso lo decide `cuadre.clients`; la base solo defiende `national` ⇔ `ES`."""
    insert_direct(admin, cast.alicia, scope="eu", country="XX")
    insert_direct(admin, cast.alicia, scope="non_eu", country="DE")


@pytest.mark.parametrize(
    ("scope", "country", "kind", "vies"),
    [
        ("national", "ES", "business", "valid_simulated"),
        ("eu", "DE", "individual", "valid_simulated"),
        ("non_eu", "MX", "business", "valid_simulated"),
        ("non_eu", "MX", "business", "unchecked"),
        ("eu", "DE", "individual", "unchecked"),
    ],
)
def test_vies_only_marks_an_eu_company(
    admin: Connection[DictRow], cast: Cast, scope: str, country: str, kind: str, vies: str
) -> None:
    assert (
        violation(admin, cast.alicia, CHECK, scope=scope, country=country, kind=kind, vies_status=vies)
        == "clients_vies_matches_scope"
    )


@pytest.mark.parametrize("vies", ["valid_simulated", "unchecked", "not_applicable"])
def test_an_eu_company_can_have_any_vies_status(admin: Connection[DictRow], cast: Cast, vies: str) -> None:
    insert_direct(admin, cast.alicia, scope="eu", country="DE", kind="business", vies_status=vies)


@pytest.mark.parametrize("tax_id", ["", "a" * 33])
def test_the_tax_id_length_check(admin: Connection[DictRow], cast: Cast, tax_id: str) -> None:
    assert violation(admin, cast.alicia, CHECK, tax_id=tax_id) == "clients_tax_id_length"


@pytest.mark.parametrize("tax_id", ["A", "a" * 32, None])
def test_tax_ids_the_check_accepts(admin: Connection[DictRow], cast: Cast, tax_id: str | None) -> None:
    insert_direct(admin, cast.alicia, tax_id=tax_id)


def test_the_address_length_check(admin: Connection[DictRow], cast: Cast) -> None:
    assert violation(admin, cast.alicia, CHECK, address="a" * 301) == "clients_address_length"
    insert_direct(admin, cast.alicia, address="a" * 300)
    insert_direct(admin, cast.alicia, address=None)


def test_a_tax_id_is_unique_among_the_active_clients_of_a_person(admin: Connection[DictRow], cast: Cast) -> None:
    insert_direct(admin, cast.alicia, name="Uno S.L.", tax_id=NIF)
    assert (
        violation(admin, cast.alicia, psycopg.errors.UniqueViolation, name="Dos S.L.", tax_id=NIF)
        == "clients_owner_tax_id_active"
    )
    insert_direct(admin, cast.beto, name="Uno S.L.", tax_id=NIF)  # el mismo en otra persona, bien


def test_clients_without_a_tax_id_never_collide(admin: Connection[DictRow], cast: Cast) -> None:
    insert_direct(admin, cast.alicia, name="Sin uno", tax_id=None)
    insert_direct(admin, cast.alicia, name="Sin dos", tax_id=None)


def test_archiving_frees_the_tax_id_and_reactivating_a_collision_is_refused_by_the_index(
    admin: Connection[DictRow], cast: Cast
) -> None:
    first = insert_direct(admin, cast.alicia, name="Uno S.L.", tax_id=NIF)
    admin.execute("update public.clients set archived_at = now() where id = %s", (first,))
    insert_direct(admin, cast.alicia, name="Dos S.L.", tax_id=NIF)
    with pytest.raises(psycopg.errors.UniqueViolation) as info:
        admin.execute("update public.clients set archived_at = null where id = %s", (first,))
    assert info.value.diag.constraint_name == "clients_owner_tax_id_active"


def test_the_client_goes_away_with_the_account_but_invoices_will_not_cascade(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select confdeltype as t from pg_constraint where conrelid = 'public.clients'::regclass and contype = 'f'"
    ).fetchone()
    assert (
        row is not None and row["t"] == "c"
    )  # CASCADE: es la ficha de la persona (las facturas de SPEC-W-007 no la usarán)


def test_the_enum_labels_are_the_ones_of_the_spec(admin: Connection[DictRow]) -> None:
    labels = {
        r["typname"]: r["labels"]
        for r in admin.execute(
            "select t.typname, array_agg(e.enumlabel::text order by e.enumsortorder) as labels from pg_type t "
            "join pg_enum e on e.enumtypid = t.oid join pg_namespace n on n.oid = t.typnamespace "
            "where n.nspname = 'public' and t.typname like 'client\\_%' group by t.typname"
        ).fetchall()
    }
    assert labels == {
        "client_scope": ["national", "eu", "non_eu"],
        "client_kind": ["business", "individual"],
        "client_vies_status": ["valid_simulated", "unchecked", "not_applicable"],
    }


# --- El trigger ------------------------------------------------------------------------------------------------------------------------


def trigger_error(admin: Connection[DictRow], sql: str, *params: Any) -> str:
    with pytest.raises(psycopg.errors.RaiseException) as info:
        admin.execute(sql, params)
    return info.value.diag.message_primary or ""


def test_updated_at_moves_when_a_client_changes(admin: Connection[DictRow], cast: Cast) -> None:
    cid = insert_direct(admin, cast.alicia, name="Toca S.L.")
    before = by_name(admin, cast.alicia, "Toca S.L.")["updated_at"]
    admin.execute("update public.clients set address = 'x' where id = %s", (cid,))
    assert by_name(admin, cast.alicia, "Toca S.L.")["updated_at"] > before


@pytest.mark.parametrize("column", ["owner_id", "id", "created_at"])
def test_identity_columns_never_change(admin: Connection[DictRow], cast: Cast, column: str) -> None:
    cid = insert_direct(admin, cast.alicia, name="Identidad S.L.")
    value: Any = {"owner_id": cast.beto.id, "id": uuid.uuid4(), "created_at": "2000-01-01"}[column]
    assert (
        trigger_error(admin, f"update public.clients set {column} = %s where id = %s", value, cid)
        == "client_immutable_column"
    )


def test_the_other_columns_do_change(admin: Connection[DictRow], cast: Cast) -> None:
    cid = insert_direct(admin, cast.alicia, name="Cambia S.L.")
    admin.execute(
        "update public.clients set name = 'Otro S.L.', address = 'Calle 1', archived_at = now() where id = %s", (cid,)
    )
    row = by_name(admin, cast.alicia, "Otro S.L.")
    assert row["address"] == "Calle 1" and row["archived_at"] is not None


# --- Las funciones: create_client -------------------------------------------------------------------------------------------------------


def test_create_stores_what_it_is_given_and_returns_the_id(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    cid = made(create(app_pool, cast.alicia))
    row = by_name(admin, cast.alicia, BASE["name"])
    assert row["id"] == cid and row["owner_id"] == cast.alicia.id
    assert (
        row["kind"],
        row["country"],
        row["scope"],
        row["tax_id"],
        row["address"],
        row["vies_status"],
        row["archived_at"],
    ) == (
        "business",
        "ES",
        "national",
        NIF,
        "Calle Inventada 4, Madrid",
        "not_applicable",
        None,
    )


def test_create_trims_and_stores_blanks_as_null(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(create(app_pool, cast.alicia, name="  Recortado S.L.  ", address="   ", tax_id="  "))
    row = by_name(admin, cast.alicia, "Recortado S.L.")
    assert (row["address"], row["tax_id"]) == (None, None)


def test_create_an_eu_company_with_its_vies_status(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(
        call(
            app_pool,
            cast.alicia,
            "create_client",
            EU["name"],
            EU["kind"],
            EU["country"],
            EU["scope"],
            EU["tax_id"],
            None,
            EU["vies_status"],
        )
    )
    row = by_name(admin, cast.alicia, "Kreativ GmbH")
    assert (row["scope"], row["vies_status"], row["address"]) == ("eu", "valid_simulated", None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", None),
        ("name", ""),
        ("name", "   "),
        ("name", "A"),
        ("name", "a" * 201),
        ("kind", None),
        ("kind", ""),
        ("kind", "empresa"),
        ("kind", "BUSINESS"),
        ("country", None),
        ("country", ""),
        ("country", "es"),
        ("country", "ESP"),
        ("country", "E1"),
        ("scope", None),
        ("scope", "x"),
        ("scope", "National"),
        ("tax_id", "a" * 33),
        ("address", "a" * 301),
        ("vies_status", None),
        ("vies_status", "x"),
        ("vies_status", "VALID"),
    ],
)
def test_create_refuses_bad_values_naming_the_field(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, field: str, value: Any
) -> None:
    out = create(app_pool, cast.alicia, **{field: value})
    assert code_of(out) == "invalid_client" and out.detail == field, (out.message, out.detail)
    assert rows(admin, cast.alicia) == []


@pytest.mark.parametrize(("scope", "country"), [("national", "DE"), ("eu", "ES"), ("non_eu", "ES"), ("national", "MX")])
def test_create_refuses_a_scope_that_does_not_match_the_country(
    app_pool: Pool, cast: Cast, scope: str, country: str
) -> None:
    out = create(app_pool, cast.alicia, scope=scope, country=country)
    assert code_of(out) == "invalid_client" and out.detail == "scope"


@pytest.mark.parametrize(
    ("scope", "kind", "vies"),
    [
        ("national", "business", "valid_simulated"),
        ("eu", "individual", "valid_simulated"),
        ("non_eu", "business", "unchecked"),
    ],
)
def test_create_refuses_a_vies_status_that_does_not_fit(
    app_pool: Pool, cast: Cast, scope: str, kind: str, vies: str
) -> None:
    country = {"national": "ES", "eu": "DE", "non_eu": "MX"}[scope]
    out = create(app_pool, cast.alicia, scope=scope, kind=kind, country=country, vies_status=vies)
    assert code_of(out) == "invalid_client" and out.detail == "vies_status"


def test_an_unknown_value_is_our_error_never_an_invalid_enum_cast(app_pool: Pool, cast: Cast) -> None:
    for field in ("kind", "scope", "vies_status"):
        assert create(app_pool, cast.alicia, **{field: "desconocido"}).sqlstate == "P0001"


def test_an_unknown_scope_or_vies_status_is_ours_even_when_every_other_field_fits(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """Hueco que encontró la mutación F14/F18 del hito 2: la coherencia con el país o el tipo los atrapaba solo por casualidad."""
    out = create(
        app_pool,
        cast.alicia,
        name="Taller",
        country="MX",
        scope="desconocido",
        tax_id="X1",
        vies_status="not_applicable",
    )
    assert code_of(out) == "invalid_client" and out.detail == "scope"
    out = create(app_pool, cast.alicia, **{**EU, "vies_status": "desconocido", "address": None})
    assert code_of(out) == "invalid_client" and out.detail == "vies_status"
    cid = made(create(app_pool, cast.alicia, **{**EU, "address": None}))
    out = update(app_pool, cast.alicia, cid, **{**EU, "vies_status": "desconocido", "address": None})
    assert code_of(out) == "invalid_client" and out.detail == "vies_status"
    out = update(
        app_pool,
        cast.alicia,
        cid,
        name="Taller",
        country="MX",
        scope="desconocido",
        tax_id="X1",
        vies_status="not_applicable",
    )
    assert code_of(out) == "invalid_client" and out.detail == "scope"
    assert len(rows(admin, cast.alicia)) == 1


def test_the_first_wrong_field_is_the_one_reported(app_pool: Pool, cast: Cast) -> None:
    out = create(app_pool, cast.alicia, name="", kind="x", country="zz")
    assert out.detail == "name"
    out = create(app_pool, cast.alicia, kind="x", country="zz")
    assert out.detail == "kind"


def test_a_tax_id_already_used_by_an_active_client_is_refused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    made(create(app_pool, cast.alicia))
    out = create(app_pool, cast.alicia, name="Otro S.L.")
    assert code_of(out) == "client_tax_id_taken"
    assert len(rows(admin, cast.alicia)) == 1


def test_the_same_tax_id_is_fine_after_archiving_and_for_another_person(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    first = made(create(app_pool, cast.alicia))
    made(create(app_pool, cast.beto))
    assert code_of(create(app_pool, cast.alicia, name="Otro S.L.")) == "client_tax_id_taken"
    assert not archive(app_pool, cast.alicia, first, True).error
    made(create(app_pool, cast.alicia, name="Otro S.L."))
    assert len(rows(admin, cast.alicia)) == 2


def test_clients_without_a_tax_id_can_repeat(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    made(create(app_pool, cast.alicia, name="Sin uno S.L.", tax_id=None, kind="individual"))
    made(create(app_pool, cast.alicia, name="Sin dos S.L.", tax_id=None, kind="individual"))
    assert len(rows(admin, cast.alicia)) == 2


# --- update_client -----------------------------------------------------------------------------------------------------------------------


def test_update_replaces_every_field(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    before = by_name(admin, cast.alicia, BASE["name"])["updated_at"]
    out = update(
        app_pool,
        cast.alicia,
        cid,
        name="Kreativ GmbH",
        kind="business",
        country="DE",
        scope="eu",
        tax_id="DE446120774",
        address=None,
        vies_status="valid_simulated",
    )
    assert not out.error, out.message
    row = by_name(admin, cast.alicia, "Kreativ GmbH")
    assert (row["id"], row["country"], row["scope"], row["tax_id"], row["address"], row["vies_status"]) == (
        cid,
        "DE",
        "eu",
        "DE446120774",
        None,
        "valid_simulated",
    )
    assert row["updated_at"] > before


def test_updating_a_client_with_its_own_tax_id_is_fine(app_pool: Pool, cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    assert not update(app_pool, cast.alicia, cid, name="Renombrado S.L.").error


def test_updating_to_a_tax_id_of_another_active_client_is_refused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    made(create(app_pool, cast.alicia))
    other = made(create(app_pool, cast.alicia, name="Otro S.L.", tax_id="B00000026"))
    assert code_of(update(app_pool, cast.alicia, other, name="Otro S.L.", tax_id=NIF)) == "client_tax_id_taken"
    assert by_name(admin, cast.alicia, "Otro S.L.")["tax_id"] == "B00000026"


def test_updating_to_the_tax_id_of_an_archived_client_is_fine(app_pool: Pool, cast: Cast) -> None:
    old = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, old, True)
    other = made(create(app_pool, cast.alicia, name="Otro S.L.", tax_id="B00000026"))
    assert not update(app_pool, cast.alicia, other, name="Otro S.L.", tax_id=NIF).error


def test_an_archived_client_cannot_be_edited(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, cid, True)
    assert code_of(update(app_pool, cast.alicia, cid, name="Nuevo S.L.")) == "client_archived"
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("kind", "x"),
        ("country", "zz"),
        ("scope", "x"),
        ("tax_id", "a" * 33),
        ("address", "a" * 301),
        ("vies_status", "x"),
    ],
)
def test_update_refuses_bad_values_naming_the_field(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, field: str, value: Any
) -> None:
    cid = made(create(app_pool, cast.alicia))
    out = update(app_pool, cast.alicia, cid, **{field: value})
    assert code_of(out) == "invalid_client" and out.detail == field
    assert by_name(admin, cast.alicia, BASE["name"])["tax_id"] == NIF


def test_the_order_of_checks_is_missing_then_archived_then_shape_then_tax_id(app_pool: Pool, cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, cid, True)
    assert code_of(update(app_pool, cast.alicia, cid, name="")) == "client_archived"  # antes de mirar la forma
    assert code_of(update(app_pool, cast.alicia, uuid.uuid4(), name="")) == "client_not_found"  # antes que todo


# --- set_client_archived ------------------------------------------------------------------------------------------------------------------


def test_archiving_and_reactivating(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    assert not archive(app_pool, cast.alicia, cid, True).error
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is not None
    assert not archive(app_pool, cast.alicia, cid, False).error
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is None


def test_archiving_twice_keeps_the_first_date_and_reactivating_an_active_one_does_nothing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    cid = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, cid, True)
    first = by_name(admin, cast.alicia, BASE["name"])["archived_at"]
    time.sleep(0.05)
    archive(app_pool, cast.alicia, cid, True)
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] == first
    archive(app_pool, cast.alicia, cid, False)
    assert not archive(app_pool, cast.alicia, cid, False).error
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is None


def test_reactivating_a_client_whose_tax_id_an_active_one_uses_is_our_error_not_the_index(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """B.1-C: el índice parcial daría un 23505 sin código útil; la función lo comprueba antes."""
    old = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, old, True)
    made(create(app_pool, cast.alicia, name="Nuevo S.L."))
    out = archive(app_pool, cast.alicia, old, False)
    assert code_of(out) == "client_tax_id_taken"
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is not None


def test_reactivating_is_fine_once_the_other_one_is_archived_or_has_another_tax_id(app_pool: Pool, cast: Cast) -> None:
    old = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, old, True)
    new = made(create(app_pool, cast.alicia, name="Nuevo S.L."))
    archive(app_pool, cast.alicia, new, True)
    assert not archive(app_pool, cast.alicia, old, False).error


def test_the_same_tax_id_of_another_person_does_not_block_reactivating(app_pool: Pool, cast: Cast) -> None:
    old = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, old, True)
    made(create(app_pool, cast.beto))
    assert not archive(app_pool, cast.alicia, old, False).error


def test_a_client_without_tax_id_reactivates_even_if_another_has_none(app_pool: Pool, cast: Cast) -> None:
    old = made(create(app_pool, cast.alicia, name="Sin uno S.L.", tax_id=None, kind="individual"))
    archive(app_pool, cast.alicia, old, True)
    made(create(app_pool, cast.alicia, name="Sin dos S.L.", tax_id=None, kind="individual"))
    assert not archive(app_pool, cast.alicia, old, False).error


def test_archiving_needs_a_boolean(app_pool: Pool, cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    out = archive(app_pool, cast.alicia, cid, None)
    assert code_of(out) == "invalid_client" and out.detail == "archived"


# --- Roles y ajenos -----------------------------------------------------------------------------------------------------------------------

CALLS = [
    ("create_client", args_of()),
    ("update_client", (uuid.uuid4(), *args_of())),
    ("set_client_archived", (uuid.uuid4(), True)),
]


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
@pytest.mark.parametrize(("function", "args"), CALLS)
def test_only_a_usuario_can_call_the_functions(
    app_pool: Pool, cast: Cast, who: str, function: str, args: tuple[Any, ...]
) -> None:
    assert call(app_pool, cast[who], function, *args).sqlstate == "42501"


@pytest.mark.parametrize("function", ["update_client", "set_client_archived"])
def test_anothers_client_looks_like_one_that_does_not_exist(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, function: str
) -> None:
    mine = made(create(app_pool, cast.alicia))
    args = {"update_client": (mine, *args_of(name="Hackeado S.L.")), "set_client_archived": (mine, True)}[function]
    foreign = call(app_pool, cast.beto, function, *args)
    missing = call(app_pool, cast.beto, function, uuid.uuid4(), *args[1:])
    assert code_of(foreign) == code_of(missing) == "client_not_found"
    row = by_name(admin, cast.alicia, BASE["name"])
    assert row["archived_at"] is None


def test_a_suspended_account_changes_nothing(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    cid = made(create(app_pool, cast.alicia))
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert create(app_pool, cast.alicia, name="Otro S.L.", tax_id=None).sqlstate == "42501"
    assert update(app_pool, cast.alicia, cid, name="Otro S.L.").sqlstate == "42501"
    assert archive(app_pool, cast.alicia, cid, True).sqlstate == "42501"
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is None


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
    cid = made(create(app_pool, cast.alicia))
    update(app_pool, cast.alicia, cid, name="Renombrado S.L.")
    archive(app_pool, cast.alicia, cid, True)
    archive(app_pool, cast.alicia, cid, False)
    assert count() == before


def test_the_functions_are_security_definer_with_an_empty_search_path_and_only_the_app_ones_reach_authenticated(
    admin: Connection[DictRow],
) -> None:
    found = admin.execute(
        "select n.nspname, p.proname, p.prosecdef, p.proconfig, has_function_privilege('authenticated', p.oid, 'EXECUTE') as auth, "
        "has_function_privilege('anon', p.oid, 'EXECUTE') as anon from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where p.proname like '%client%' and n.nspname in ('app', 'private') order by 1, 2"
    ).fetchall()
    names = {(r["nspname"], r["proname"]) for r in found}
    assert names == {
        ("app", "create_client"),
        ("app", "update_client"),
        ("app", "set_client_archived"),
        ("private", "clients_enter"),
        ("private", "clients_lock_own"),
        ("private", "clients_tax_id_taken"),
        ("private", "clients_validate"),
        ("private", "clients_guard"),
    }
    for r in found:
        assert r["anon"] is False, r["proname"]
        assert r["auth"] is (r["nspname"] == "app"), r["proname"]
        if r["proname"] != "clients_guard":
            assert r["proconfig"] and any(
                c.replace(" ", "") in ('search_path=""', "search_path=") for c in r["proconfig"]
            ), r["proname"]
    for r in (r for r in found if r["nspname"] == "app"):
        assert r["prosecdef"] is True


# --- Concurrencia: el cerrojo por persona -------------------------------------------------------------------------------------------------


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


def test_two_creations_with_the_same_tax_id_give_our_error_not_a_unique_violation(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """B.1-C: sin cerrojo, la segunda fallaba con 23505 en el índice. Con él espera y ve lo que hizo la primera."""
    waited, second = run_while_holding(
        app_pool, cast.alicia, "create_client", args_of(), "create_client", args_of(name="Otro S.L.")
    )
    assert waited, "la segunda operación no esperó a la primera"
    assert code_of(second) == "client_tax_id_taken"
    assert len(rows(admin, cast.alicia)) == 1


def test_a_creation_and_a_reactivation_with_the_same_tax_id_at_the_same_time(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    old = made(create(app_pool, cast.alicia))
    archive(app_pool, cast.alicia, old, True)
    waited, second = run_while_holding(
        app_pool, cast.alicia, "create_client", args_of(name="Nuevo S.L."), "set_client_archived", (old, False)
    )
    assert waited
    assert code_of(second) == "client_tax_id_taken"
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is not None


def test_the_lock_is_per_person_not_global(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """Mientras Alicia tiene el cerrojo, Beto no espera."""
    waited, second = run_while_holding(
        app_pool, cast.alicia, "create_client", args_of(), "create_client", args_of(), other=cast.beto
    )
    assert not waited, "Beto esperó a Alicia"
    assert not second.error
    assert len(rows(admin, cast.beto)) == 1


def test_the_lock_is_taken_even_by_the_functions_that_do_not_create(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    cid = made(create(app_pool, cast.alicia))
    waited, second = run_while_holding(
        app_pool, cast.alicia, "set_client_archived", (cid, True), "update_client", (cid, *args_of(name="Nuevo S.L."))
    )
    assert waited
    assert code_of(second) == "client_archived"  # esperó, vio el archivado de la primera y se negó
    assert by_name(admin, cast.alicia, BASE["name"])["archived_at"] is not None
