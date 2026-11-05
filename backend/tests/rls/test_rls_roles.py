"""NFR-06 · `test_rls_roles`: 0 accesos indebidos entre usuario, gestor y administrador (AC-06, AC-07, AC-08, AC-09, AC-10, AC-11).

La lectura se compara con `rls_matrix.yaml` para cada tabla, persona y estado del vínculo Alicia -> Gina. Las escrituras ajenas
se prueban de forma genérica por tabla; los flujos concretos del gestor y del administrador tienen sus propios archivos.
"""

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import KEYS, Cast, Pool, apply_scenario, attempt, call, load_matrix, visible_owners

MATRIX = load_matrix()
TABLES = sorted(MATRIX["tables"])
SCENARIOS = MATRIX["scenarios"]


def expected_for(table: str, scenario: str, key: str) -> list[str] | str:
    select = MATRIX["tables"][table]["select"]
    return select.get(scenario, {}).get(key, select["default"][key])


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("table", TABLES)
def test_each_person_sees_exactly_what_the_matrix_says(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, table: str, scenario: str
) -> None:
    if seed := MATRIX["tables"][table].get("seed"):
        for owner in (cast.alicia, cast.beto):
            admin.execute(seed, {"owner": owner.id})
    apply_scenario(app_pool, cast, scenario)
    owner_column = MATRIX["tables"][table]["owner_column"]
    for key in KEYS:
        expected = expected_for(table, scenario, key)
        visible = visible_owners(app_pool, cast[key], table, owner_column)
        if expected == "all":
            # El administrador ve metadatos de todas las cuentas (también las de otros tests): al menos todo el reparto.
            assert cast.ids() <= visible, f"{table}/{scenario}: {key} debería ver a todo el reparto"
        else:
            wanted = {cast[k].id for k in expected}
            assert visible == wanted, (
                f"{table}/{scenario}: {key} ve {_names(cast, visible)}, esperado {sorted(expected)}"
            )


def _names(cast: Cast, ids: set) -> list[str]:
    by_id = {p.id: p.key for p in cast.everyone()}
    return sorted(by_id.get(i, "ajeno") for i in ids)


@pytest.mark.parametrize("key", ["beto", "gus", "gina", "adan"])
@pytest.mark.parametrize("table", TABLES)
def test_nobody_else_can_write_alicias_rows(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, table: str, key: str
) -> None:
    """Beto (otro usuario), Gus (gestor sin vínculo), Gina (gestor con vínculo ACTIVO) y Adán (admin) no escriben en lo de Alicia."""
    apply_scenario(app_pool, cast, "active")
    spec = MATRIX["tables"][table]
    owner_column, probe = spec["owner_column"], spec["probe_update"]
    actor, alicia = cast[key], cast.alicia
    params = {"owner": alicia.id, "email": f"x.{alicia.email}", "value": probe["value"]}

    update = attempt(
        app_pool,
        actor,
        f'update public."{table}" set "{probe["column"]}" = %(value)s where "{owner_column}" = %(owner)s',
        params,
    )
    delete = attempt(app_pool, actor, f'delete from public."{table}" where "{owner_column}" = %(owner)s', params)
    insert = attempt(app_pool, actor, spec["probe_insert"], params)

    assert update.blocked, f"{key} modificó {table} de Alicia"
    assert delete.blocked, f"{key} borró de {table} de Alicia"
    assert insert.error, f"{key} insertó en {table} a nombre de Alicia"

    # Comprobación con privilegios de administrador de la base de datos: nada ha cambiado.
    changed = admin.execute(
        f'select count(*) as n from public."{table}" where "{owner_column}" = %s and "{probe["column"]}"::text = %s',
        (alicia.id, probe["value"]),
    ).fetchone()
    assert changed is not None and changed["n"] == 0


def test_the_owner_updates_only_the_granted_columns(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    alicia = cast.alicia
    assert (
        attempt(
            app_pool, alicia, "update public.profiles set display_name = 'Alicia B.' where id = %s", (alicia.id,)
        ).rowcount
        == 1
    )
    tax = attempt(
        app_pool, alicia, "update public.business_profiles set tax_id = 'TEST-1' where owner_id = %s", (alicia.id,)
    )
    assert tax.rowcount == 1

    forbidden = {
        "role": "'admin'",
        "status": "'suspended'",
        "email": "'otro@example.test'",
        "id": "gen_random_uuid()",
        "created_at": "now()",
    }
    for column, literal in forbidden.items():
        out = attempt(app_pool, alicia, f"update public.profiles set {column} = {literal} where id = %s", (alicia.id,))
        assert out.sqlstate == "42501", f"Alicia pudo actualizar profiles.{column}"
    moved = attempt(
        app_pool,
        alicia,
        "update public.business_profiles set owner_id = %s where owner_id = %s",
        (cast.beto.id, alicia.id),
    )
    assert moved.sqlstate == "42501"

    profile = admin.execute(
        "select role, status, display_name from public.profiles where id = %s", (alicia.id,)
    ).fetchone()
    assert profile == {"role": "usuario", "status": "active", "display_name": "Alicia B."}


def test_no_privilege_escalation(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """AC-06 · Un usuario no puede darse (ni dar) un rol superior."""
    alicia = cast.alicia
    assert (
        attempt(app_pool, alicia, "update public.profiles set role = 'admin' where id = %s", (alicia.id,)).sqlstate
        == "42501"
    )
    assert call(app_pool, alicia, "admin_set_role", alicia.id, "admin").sqlstate == "42501"
    assert call(app_pool, alicia, "admin_set_role", cast.beto.id, "admin").sqlstate == "42501"
    assert call(app_pool, alicia, "admin_set_status", cast.beto.id, "suspended").sqlstate == "42501"
    roles = admin.execute(
        "select id, role from public.profiles where id = any(%s)", ([alicia.id, cast.beto.id],)
    ).fetchall()
    assert {r["role"] for r in roles} == {"usuario"}


def test_a_gestor_cannot_use_the_admin_functions(app_pool: Pool, cast: Cast) -> None:
    assert call(app_pool, cast.gina, "admin_set_role", cast.gina.id, "admin").sqlstate == "42501"
    assert call(app_pool, cast.gina, "admin_set_role", cast.alicia.id, "gestor").sqlstate == "42501"


@pytest.mark.parametrize("table", TABLES)
def test_anon_cannot_touch_anything(app_pool: Pool, table: str) -> None:
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege), app_pool.connection() as conn:
        conn.execute("SET LOCAL ROLE anon")
        conn.execute(f'select * from public."{table}"')


@pytest.mark.parametrize("table", TABLES)
def test_the_login_role_has_no_direct_access(app_pool: Pool, table: str) -> None:
    """cuadre_app no tiene privilegios propios: una consulta que olvide SET LOCAL ROLE falla en vez de saltarse la RLS."""
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege), app_pool.connection() as conn:
        conn.execute(f'select * from public."{table}"')
