"""§5.2 y B.3 «Para el hito 3» · La traducción de los errores de la base a `problem+json`, con errores REALES de PostgreSQL."""

import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.clients import repository
from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction
from tests.support import Cast, Person, Pool

ARGS = ("Estudio Norte S.L.", "business", "ES", "national", "B00000018", None, "not_applicable")


def raised(pool: Pool, person: Person, sql: str, params: Any = None) -> psycopg.Error:
    with pytest.raises(psycopg.Error) as info, user_transaction(pool, person.id) as conn:
        conn.execute(sql, params)
    return info.value


def translated(exc: psycopg.Error) -> ProblemError | None:
    return repository.translate_db_error(exc)


def call(pool: Pool, person: Person, function: str, *args: Any) -> psycopg.Error:
    marks = ", ".join(["%s"] * len(args))
    return raised(pool, person, f"select app.{function}({marks})", args)


def made(pool: Pool, person: Person) -> uuid.UUID:
    with user_transaction(pool, person.id) as conn:
        row = conn.execute("select app.create_client(%s, %s, %s, %s, %s, %s, %s) as id", ARGS).fetchone()
        assert row is not None
        return row["id"]


def test_a_missing_client_is_a_404(app_pool: Pool, cast: Cast) -> None:
    problem = translated(call(app_pool, cast.alicia, "set_client_archived", uuid.uuid4(), True))
    assert problem is not None and (problem.status, problem.code) == (404, "client_not_found")


def test_an_archived_client_is_a_409(app_pool: Pool, cast: Cast) -> None:
    cid = made(app_pool, cast.alicia)
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select app.set_client_archived(%s, true)", (cid,))
    problem = translated(call(app_pool, cast.alicia, "update_client", cid, *ARGS))
    assert problem is not None and (problem.status, problem.code) == (409, "client_archived")


def test_a_repeated_tax_id_is_a_409(app_pool: Pool, cast: Cast) -> None:
    made(app_pool, cast.alicia)
    problem = translated(call(app_pool, cast.alicia, "create_client", *ARGS))
    assert problem is not None and (problem.status, problem.code) == (409, "client_tax_id_taken")


def test_the_unique_index_violation_is_also_a_409_the_safety_net(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    """Con el cerrojo no debería darse; si se diera (otro escritor), la persona vería nuestro error y no un 500."""
    made(app_pool, cast.alicia)
    with pytest.raises(psycopg.errors.UniqueViolation) as info:
        admin.execute(
            "insert into public.clients (owner_id, name, kind, country, scope, tax_id) values (%s, 'Otro S.L.', 'business', 'ES', 'national', 'B00000018')",
            (cast.alicia.id,),
        )
    problem = translated(info.value)
    assert problem is not None and (problem.status, problem.code) == (409, "client_tax_id_taken")


def test_another_unique_violation_is_not_ours(admin: Connection[DictRow], cast: Cast) -> None:
    with pytest.raises(psycopg.errors.UniqueViolation) as info:
        admin.execute("insert into public.profiles (id, email) values (%s, %s)", (uuid.uuid4(), cast.alicia.email))
    assert translated(info.value) is None


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_role_that_is_not_usuario_is_a_403(app_pool: Pool, cast: Cast, who: str) -> None:
    problem = translated(call(app_pool, cast[who], "create_client", *ARGS))
    assert problem is not None and (problem.status, problem.code) == (403, "forbidden")


def test_a_shape_error_of_the_function_is_not_translated_it_is_ours_to_fix(app_pool: Pool, cast: Cast) -> None:
    """La API valida antes con el dominio: que la base responda `invalid_client` es un fallo de construcción (500 sin detalles)."""
    exc = call(app_pool, cast.alicia, "create_client", "", "business", "ES", "national", None, None, "not_applicable")
    assert exc.diag.message_primary == "invalid_client" and exc.diag.message_detail == "name"
    assert translated(exc) is None


def test_a_check_violation_is_not_translated(admin: Connection[DictRow], cast: Cast) -> None:
    with pytest.raises(psycopg.errors.CheckViolation) as info:
        admin.execute(
            "insert into public.clients (owner_id, name, kind, country, scope) values (%s, 'Mal S.L.', 'business', 'DE', 'national')",
            (cast.alicia.id,),
        )
    assert translated(info.value) is None


def test_an_invalid_enum_cast_is_not_translated(admin: Connection[DictRow], cast: Cast) -> None:
    with pytest.raises(psycopg.errors.InvalidTextRepresentation) as info:
        admin.execute(
            "insert into public.clients (owner_id, name, kind, country, scope) values (%s, 'Mal S.L.', 'otro', 'ES', 'national')",
            (cast.alicia.id,),
        )
    assert translated(info.value) is None


def test_an_unknown_message_of_ours_is_not_translated(admin: Connection[DictRow]) -> None:
    with pytest.raises(psycopg.errors.RaiseException) as info:
        admin.execute("do $$ begin raise exception 'algo_inesperado' using errcode = 'P0001'; end $$")
    assert translated(info.value) is None


def test_the_identity_trigger_error_is_not_translated(admin: Connection[DictRow], app_pool: Pool, cast: Cast) -> None:
    cid = made(app_pool, cast.alicia)
    with pytest.raises(psycopg.errors.RaiseException) as info:
        admin.execute("update public.clients set owner_id = %s where id = %s", (cast.beto.id, cid))
    assert info.value.diag.message_primary == "client_immutable_column"
    assert translated(info.value) is None
