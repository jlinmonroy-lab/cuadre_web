"""Hito 1 + hito 2 · Los motivos de fallo del cliente de agentes son exactamente los que admite la base de datos (SPEC-W-002 §5.1)."""

import re

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import FailureCode
from tests.support import Cast, Pool, advance, call, new_document


def database_error_codes(admin: Connection[DictRow]) -> set[str]:
    row = admin.execute(
        "select pg_get_constraintdef(oid) as definition from pg_constraint "
        "where conrelid = 'public.documents'::regclass and contype = 'c' "
        "and pg_get_constraintdef(oid) like '%%error_code = ANY%%'"
    ).fetchone()
    assert row is not None, "la CHECK de documents.error_code no existe"
    return set(re.findall(r"'([a-z_]+)'::text", row["definition"]))


def test_the_failure_codes_are_the_ones_the_check_constraint_allows(admin: Connection[DictRow]) -> None:
    assert {code.value for code in FailureCode} == database_error_codes(admin)


@pytest.mark.parametrize("code", list(FailureCode), ids=lambda c: c.value)
def test_every_failure_code_can_be_recorded_through_the_database_function(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, code: FailureCode
) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "processing")
    out = call(app_pool, cast.alicia, "fail_extraction", doc.id, code.value)
    assert not out.error, out.message
    row = admin.execute(
        "select status::text as status, error_code from public.documents where id = %s", (doc.id,)
    ).fetchone()
    assert row == {"status": "extraction_failed", "error_code": code.value}
