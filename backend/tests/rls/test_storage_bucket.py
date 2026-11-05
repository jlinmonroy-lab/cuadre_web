"""SPEC-W-002 hito 0 · El bucket `documents` existe, es privado y tiene los límites de la spec (ADR-0004).

Las políticas de `storage.objects` llegan con la tabla `documents` (hito 1) y las prueba `test_storage_policies.py`. Aquí solo se vigila lo que
no puede cambiar nunca: que el bucket no sea público, que sus límites coincidan con los de la CHECK de `documents` y la API (15 MiB, cinco
tipos) y que `anon` no tenga ninguna política sobre los archivos.
"""

from psycopg import Connection
from psycopg.rows import DictRow

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/heic", "image/webp"}


def documents_bucket(admin: Connection[DictRow]) -> DictRow:
    row = admin.execute(
        "select id, public, file_size_limit, allowed_mime_types from storage.buckets where id = 'documents'"
    ).fetchone()
    assert row is not None, "falta el bucket «documents»: ¿se aplicó la migración?"
    return row


def test_the_documents_bucket_is_private(admin: Connection[DictRow]) -> None:
    assert documents_bucket(admin)["public"] is False


def test_the_bucket_limits_are_the_ones_in_the_spec(admin: Connection[DictRow]) -> None:
    bucket = documents_bucket(admin)
    assert bucket["file_size_limit"] == MAX_UPLOAD_BYTES
    assert set(bucket["allowed_mime_types"]) == ALLOWED_MIME_TYPES


def test_no_other_bucket_is_public(admin: Connection[DictRow]) -> None:
    rows = admin.execute("select id from storage.buckets where public").fetchall()
    assert rows == []


def test_storage_objects_has_rls_enabled(admin: Connection[DictRow]) -> None:
    row = admin.execute("select relrowsecurity as rls from pg_class where oid = 'storage.objects'::regclass").fetchone()
    assert row is not None and row["rls"] is True


def test_anon_has_no_policy_on_storage_objects(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select policyname, roles from pg_policies where schemaname = 'storage' and tablename = 'objects'"
    ).fetchall()
    offenders = [r["policyname"] for r in rows if {"anon", "public"} & set(r["roles"])]
    assert offenders == []
