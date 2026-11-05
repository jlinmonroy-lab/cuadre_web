"""AC-07 · Quién puede qué sobre `documents` y sus funciones `app.*` (SPEC-W-002 §5.2, T2-06).

La lectura de cada persona en cada estado del vínculo la compara `test_rls_roles` con `rls_matrix.yaml`. Aquí van las reglas de las
funciones: solo `usuario` escribe, un documento ajeno es indistinguible de uno inexistente y el gestor pierde el acceso al revocar.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from tests.support import (
    GOOD_EXTRACTION,
    Cast,
    Doc,
    Outcome,
    Person,
    Pool,
    advance,
    attempt,
    call,
    invite,
    new_document,
    visible_owners,
)

# función de app.* -> argumentos para un documento
CALLS: dict[str, Callable[[uuid.UUID], tuple[Any, ...]]] = {
    "mark_document_uploaded": lambda d: (d,),
    "record_extraction": lambda d: (d, Jsonb(GOOD_EXTRACTION), False, None, None),
    "fail_extraction": lambda d: (d, "unreadable"),
    "retry_document": lambda d: (d,),
    "save_document_review": lambda d: (d, Jsonb({})),
    "discard_document": lambda d: (d,),
}


def run(pool: Pool, person: Person, function: str, doc_id: uuid.UUID) -> Outcome:
    args = CALLS[function](doc_id)
    return attempt(pool, person, f"select app.{function}({', '.join(['%s'] * len(args))})", args)


def reads(pool: Pool, person: Person, doc: Doc) -> bool:
    out = attempt(pool, person, "select id from public.documents where id = %s", (doc.id,))
    assert not out.error, out.message
    return bool(out.rows)


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_only_usuario_can_create_documents(app_pool: Pool, cast: Cast, who: str) -> None:
    out = attempt(app_pool, cast[who], "select app.create_document('f.pdf', 'application/pdf', 10, 'file')")
    assert out.sqlstate == "42501"


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
@pytest.mark.parametrize("function", sorted(CALLS))
def test_gestor_and_admin_cannot_touch_a_document_even_with_active_access(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str, function: str
) -> None:
    doc = new_document(app_pool, cast.alicia)
    advance(app_pool, cast.alicia, doc, "processing")
    link = invite(app_pool, cast.alicia, cast.gina)
    assert not call(app_pool, cast.gina, "accept_gestor_access", link).error

    out = run(app_pool, cast[who], function, doc.id)

    assert out.sqlstate == "42501", f"{who} pudo llamar a {function}"
    row = admin.execute("select status, review from public.documents where id = %s", (doc.id,)).fetchone()
    assert row == {"status": "processing", "review": None}


@pytest.mark.parametrize("function", sorted(CALLS))
def test_a_foreign_document_looks_exactly_like_a_missing_one(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, function: str
) -> None:
    doc = new_document(app_pool, cast.alicia)
    advance(app_pool, cast.alicia, doc, "processing")

    foreign = run(app_pool, cast.beto, function, doc.id)
    missing = run(app_pool, cast.beto, function, uuid.uuid4())

    assert foreign.sqlstate == missing.sqlstate == "P0001"
    assert foreign.message == missing.message
    assert "document_not_found" in (foreign.message or "")
    row = admin.execute("select status, review from public.documents where id = %s", (doc.id,)).fetchone()
    assert row == {"status": "processing", "review": None}


def test_a_suspended_account_cannot_write_but_still_reads_its_own(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = new_document(app_pool, cast.alicia)
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))

    assert (
        attempt(app_pool, cast.alicia, "select app.create_document('f.pdf', 'application/pdf', 10, 'file')").sqlstate
        == "42501"
    )
    assert run(app_pool, cast.alicia, "discard_document", doc.id).sqlstate == "42501"
    assert reads(app_pool, cast.alicia, doc)


def test_the_gestor_reads_a_document_only_while_the_link_is_active(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = new_document(app_pool, cast.alicia)
    other = new_document(app_pool, cast.beto)
    assert not reads(app_pool, cast.gina, doc)

    link = invite(app_pool, cast.alicia, cast.gina)
    assert not reads(app_pool, cast.gina, doc), "una invitación pendiente no da acceso"

    assert not call(app_pool, cast.gina, "accept_gestor_access", link).error
    assert reads(app_pool, cast.gina, doc)
    assert not reads(app_pool, cast.gina, other), "solo los documentos de quien le dio acceso"
    assert not reads(app_pool, cast.gus, doc), "otro gestor sin vínculo no lee"
    assert not reads(app_pool, cast.beto, doc)
    assert not reads(app_pool, cast.adan, doc), "el administrador no ve datos financieros (D3)"

    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert not reads(app_pool, cast.gina, doc), "revocar corta el acceso en la petición siguiente"
    assert visible_owners(app_pool, cast.alicia, "documents", "owner_id") == {cast.alicia.id}


@pytest.mark.parametrize("who", ["alicia", "gina", "adan"])
def test_nobody_writes_documents_directly(app_pool: Pool, cast: Cast, who: str) -> None:
    doc = new_document(app_pool, cast.alicia)
    statements = [
        (
            "insert into public.documents (owner_id, source, original_filename, mime_type, size_bytes, storage_path) "
            "values (%s, 'file', 'x.pdf', 'application/pdf', 1, 'x')",
            (cast[who].id,),
        ),
        ("update public.documents set error_code = 'timeout' where id = %s", (doc.id,)),
        ("delete from public.documents where id = %s", (doc.id,)),
        ("truncate public.documents", ()),
    ]
    for sql, params in statements:
        assert attempt(app_pool, cast[who], sql, params).sqlstate == "42501", f"{who}: {sql.split()[0]}"
