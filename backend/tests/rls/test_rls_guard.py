"""AC-13 · Ninguna tabla queda sin RLS, sin registrar ni con privilegios de más.

Es la guardia anti-olvido de NFR-06: una tabla nueva de `public` sin RLS forzada, sin figurar en `rls_matrix.yaml` o con
privilegios que no declara la matriz hace fallar este archivo.
"""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import load_matrix

TABLE_PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN"]
COLUMN_PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "REFERENCES"]
MATRIX = load_matrix()["tables"]


def public_tables(admin: Connection[DictRow]) -> list[dict[str, Any]]:
    return admin.execute(
        """
        select c.relname as name, c.relrowsecurity as rls, c.relforcerowsecurity as forced
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind in ('r', 'p') order by 1
        """
    ).fetchall()


def problems(admin: Connection[DictRow]) -> list[str]:
    """Tablas de `public` sin RLS activada y forzada, o sin registrar en la matriz."""
    found = []
    for table in public_tables(admin):
        if not (table["rls"] and table["forced"]):
            found.append(f"{table['name']}: RLS no activada y forzada")
        if table["name"] not in MATRIX:
            found.append(f"{table['name']}: no figura en rls_matrix.yaml")
    return found


def columns(admin: Connection[DictRow], table: str) -> list[str]:
    rows = admin.execute(
        "select column_name from information_schema.columns where table_schema = 'public' and table_name = %s", (table,)
    ).fetchall()
    return [r["column_name"] for r in rows]


def has_table_priv(admin: Connection[DictRow], role: str, table: str, privilege: str) -> bool:
    row = admin.execute("select has_table_privilege(%s, %s, %s) as ok", (role, f"public.{table}", privilege)).fetchone()
    assert row is not None
    return row["ok"]


def has_column_priv(admin: Connection[DictRow], role: str, table: str, column: str, privilege: str) -> bool:
    row = admin.execute(
        "select has_column_privilege(%s, %s, %s, %s) as ok", (role, f"public.{table}", column, privilege)
    ).fetchone()
    assert row is not None
    return row["ok"]


def test_every_public_table_has_forced_rls_and_is_registered(admin: Connection[DictRow]) -> None:
    assert problems(admin) == []


def test_the_matrix_has_no_ghost_tables(admin: Connection[DictRow]) -> None:
    existing = {t["name"] for t in public_tables(admin)}
    assert set(MATRIX) <= existing, f"tablas en la matriz que no existen: {set(MATRIX) - existing}"


def test_the_guard_detects_a_table_without_rls(admin: Connection[DictRow]) -> None:
    with admin.transaction(force_rollback=True):
        admin.execute("create table public.zz_guard_probe (id int)")
        found = problems(admin)
    assert any("zz_guard_probe: RLS no activada" in p for p in found)
    assert any("zz_guard_probe: no figura" in p for p in found)


def test_no_policy_mentions_user_metadata(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select tablename, policyname, coalesce(qual, '') || ' ' || coalesce(with_check, '') as text "
        "from pg_policies where schemaname = 'public'"
    ).fetchall()
    offenders = [r for r in rows if "user_metadata" in r["text"] or "raw_user_meta_data" in r["text"]]
    assert offenders == []


def test_no_function_reads_user_metadata_for_authorization(admin: Connection[DictRow]) -> None:
    """handle_new_user lee display_name de raw_user_meta_data a propósito; ninguna otra función puede tocarlo."""
    rows = admin.execute(
        """
        select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname in ('private', 'app', 'public')
          and (p.prosrc ilike '%user_metadata%' or p.prosrc ilike '%raw_user_meta_data%')
        """
    ).fetchall()
    assert {r["proname"] for r in rows} <= {"handle_new_user"}


def test_every_policy_is_for_authenticated_only(admin: Connection[DictRow]) -> None:
    rows = admin.execute("select tablename, policyname, roles from pg_policies where schemaname = 'public'").fetchall()
    assert rows, "no hay ninguna política"
    for row in rows:
        assert set(row["roles"]) == {"authenticated"}, f"{row['tablename']}.{row['policyname']} aplica a {row['roles']}"


@pytest.mark.parametrize("table", sorted(MATRIX))
def test_anon_has_no_privileges(admin: Connection[DictRow], table: str) -> None:
    for privilege in TABLE_PRIVILEGES:
        assert not has_table_priv(admin, "anon", table, privilege), f"anon tiene {privilege} sobre {table}"
    for column in columns(admin, table):
        for privilege in COLUMN_PRIVILEGES:
            assert not has_column_priv(admin, "anon", table, column, privilege), (
                f"anon: {privilege} en {table}.{column}"
            )


@pytest.mark.parametrize("table", sorted(MATRIX))
def test_authenticated_privileges_match_the_matrix(admin: Connection[DictRow], table: str) -> None:
    grants = MATRIX[table]["grants"]
    table_level = set(grants.get("table", []))
    column_level = grants.get("columns", {})
    for privilege in TABLE_PRIVILEGES:
        expected = privilege in table_level
        assert has_table_priv(admin, "authenticated", table, privilege) == expected, (
            f"{table}: {privilege} a nivel de tabla"
        )
    for column in columns(admin, table):
        for privilege in COLUMN_PRIVILEGES:
            expected = privilege in table_level or column in column_level.get(privilege, [])
            actual = has_column_priv(admin, "authenticated", table, column, privilege)
            assert actual == expected, f"{table}.{column}: {privilege} esperado={expected}"


@pytest.mark.parametrize("table", sorted(MATRIX))
def test_service_role_has_no_destructive_privileges(admin: Connection[DictRow], table: str) -> None:
    for privilege in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN"):
        assert not has_table_priv(admin, "service_role", table, privilege), (
            f"service_role tiene {privilege} sobre {table}"
        )


def helper_functions(admin: Connection[DictRow]) -> list[dict[str, Any]]:
    return admin.execute(
        """
        select n.nspname as schema, p.proname as name, p.oid::regprocedure::text as signature,
               p.prosecdef as definer, p.proconfig as config, p.oid as oid
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname in ('private', 'app') order by 1, 2
        """
    ).fetchall()


def test_security_definer_functions_pin_an_empty_search_path(admin: Connection[DictRow]) -> None:
    functions = helper_functions(admin)
    assert functions, "no hay funciones en private/app"
    for fn in functions:
        if fn["definer"]:
            config = [c.replace('"', "") for c in (fn["config"] or [])]
            assert "search_path=" in config, f"{fn['signature']} es SECURITY DEFINER sin search_path vacío"


def test_no_function_is_executable_by_anon_or_public(admin: Connection[DictRow]) -> None:
    for fn in helper_functions(admin):
        row = admin.execute("select has_function_privilege('anon', %s, 'EXECUTE') as ok", (fn["oid"],)).fetchone()
        assert row is not None and not row["ok"], f"anon puede ejecutar {fn['signature']}"


def test_log_activity_is_not_executable_by_authenticated(admin: Connection[DictRow]) -> None:
    """Si authenticated pudiera ejecutarla, cualquiera falsificaría entradas del registro de actividad."""
    fn = next(f for f in helper_functions(admin) if f["name"] == "log_activity")
    row = admin.execute("select has_function_privilege('authenticated', %s, 'EXECUTE') as ok", (fn["oid"],)).fetchone()
    assert row is not None and not row["ok"]
