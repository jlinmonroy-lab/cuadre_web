"""AC-12, D-03 · Límites: 5 lecturas simultáneas por persona, y que los números repetidos en SQL y en la API coinciden.

El 5 vive en SQL (hito 1); aquí se comprueba que la API lo respeta y lo traduce a 429 con `Retry-After`. Los 15 MiB, los cinco tipos y
los 120 s existen en tres sitios (CHECK, bucket y API; SQL y API): un test los compara para que subir uno sin los otros falle.
"""

import re
from typing import Any
from uuid import UUID

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from cuadre.documents import limits, models, repository
from tests.documents.conftest import Api, age, db_row
from tests.support import Pool, call


def documents_of(admin: Connection[DictRow], person_id: UUID) -> int:
    row = admin.execute("select count(*) as n from public.documents where owner_id = %s", (person_id,)).fetchone()
    assert row is not None
    return int(row["n"])


def five_reading(api: Api, app_pool: Pool, person: Any) -> list[UUID]:
    ids = []
    for _ in range(5):
        document_id = api.uploaded(person)
        assert not call(app_pool, person, "mark_document_uploaded", document_id).error
        ids.append(document_id)
    return ids


# --- AC-12 -----------------------------------------------------------------------------------------------------------------------


def test_ac12_with_five_readings_in_progress_a_new_upload_is_429_and_creates_no_row(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    five_reading(api, app_pool, alicia)
    before = documents_of(admin, alicia.id)
    signed_before = len(api.storage.operations("sign_upload"))

    response = api.reserve(alicia)
    assert response.status_code == 429, response.text
    assert response.json()["code"] == "too_many_processing"
    assert response.headers["retry-after"] == "10"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert documents_of(admin, alicia.id) == before, "no se crea ninguna fila"
    assert len(api.storage.operations("sign_upload")) == signed_before, "ni se llega a firmar una subida"

    assert api.reserve(beto).status_code == 201, "el límite es por persona"


def test_a_reading_that_has_been_silent_for_more_than_120_seconds_does_not_take_a_place(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    ids = five_reading(api, app_pool, alicia)
    assert api.reserve(alicia).status_code == 429
    age(admin, ids[0], 121)
    assert api.reserve(alicia).status_code == 201


def test_completing_with_five_readings_in_progress_is_429_and_the_document_stays_uploading(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    waiting = api.uploaded(alicia)  # reservado ANTES de llenar el cupo
    readers = five_reading(api, app_pool, alicia)
    api.script("invoice_ok")

    response = api.complete(alicia, waiting)
    assert response.status_code == 429 and response.json()["code"] == "too_many_processing"
    assert response.headers["retry-after"] == "10"
    assert db_row(admin, waiting)["status"] == "uploading"
    assert len(api.app.state.agents_client.calls) == 0

    assert api.discard(alicia, readers[0]).status_code == 204  # se libera un sitio
    assert api.complete(alicia, waiting).json()["status"] == "review"


def test_retrying_with_five_readings_in_progress_is_429_and_the_document_stays_failed(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.script(AgentsError(FailureCode.unreadable, http_status=422))
    failed = api.read(alicia)
    five_reading(api, app_pool, alicia)
    api.script("invoice_ok")

    response = api.retry(alicia, failed)
    assert response.status_code == 429 and response.headers["retry-after"] == "10"
    assert db_row(admin, failed)["status"] == "extraction_failed"
    assert len(api.app.state.agents_client.calls) == 0


# --- Coherencia con SQL ------------------------------------------------------------------------------------------------------


def constraint(admin: Connection[DictRow], fragment: str) -> str:
    row = admin.execute(
        "select pg_get_constraintdef(oid) as definition from pg_constraint "
        "where conrelid = 'public.documents'::regclass and contype = 'c' and pg_get_constraintdef(oid) like %s",
        (f"%{fragment}%",),
    ).fetchone()
    assert row is not None, f"no hay CHECK con {fragment!r}"
    return str(row["definition"])


def test_the_15_mib_limit_is_the_same_in_the_check_the_bucket_and_the_api(admin: Connection[DictRow]) -> None:
    assert limits.MAX_UPLOAD_BYTES == 15728640
    check = constraint(admin, "size_bytes <=")
    assert re.findall(r"size_bytes <= (\d+)", check) == [str(limits.MAX_UPLOAD_BYTES)]
    bucket = admin.execute("select file_size_limit from storage.buckets where id = 'documents'").fetchone()
    assert bucket is not None and bucket["file_size_limit"] == limits.MAX_UPLOAD_BYTES


def test_the_five_types_are_the_same_in_the_check_the_bucket_and_the_api(admin: Connection[DictRow]) -> None:
    expected = set(limits.MIME_EXTENSIONS)
    assert len(expected) == 5
    check = constraint(admin, "mime_type = ANY")
    assert set(re.findall(r"'([a-z]+/[a-z]+)'::text", check)) == expected
    bucket = admin.execute("select allowed_mime_types from storage.buckets where id = 'documents'").fetchone()
    assert bucket is not None and set(bucket["allowed_mime_types"]) == expected


def test_each_extension_matches_the_path_the_database_builds(api: Api) -> None:
    alicia = api.cast.alicia
    for mime, extension in limits.MIME_EXTENSIONS.items():
        document_id = UUID(api.reserve(alicia, mime=mime).json()["id"])
        assert api.storage.operations("sign_upload")[-1].path == f"{alicia.id}/{document_id}.{extension}"


def test_the_120_seconds_are_the_same_in_sql_and_in_the_api(admin: Connection[DictRow]) -> None:
    row = admin.execute("select extract(epoch from private.document_processing_timeout())::int as seconds").fetchone()
    assert row is not None and row["seconds"] == limits.PROCESSING_TIMEOUT_SECONDS
    assert limits.READ_URL_SECONDS == 120 and limits.PREVIEW_URL_SECONDS == 60  # NFR-11: las URL firmadas son cortas


def test_every_failure_code_has_a_message_and_the_api_models_know_every_code() -> None:
    assert set(limits.FAILURE_MESSAGES) == set(FailureCode)
    assert set(models.FailureCodeName.__args__) == {c.value for c in FailureCode}  # type: ignore[attr-defined]
    assert all(text.endswith(".") and "{" not in text for text in limits.FAILURE_MESSAGES.values())


def test_the_list_is_capped(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    alicia = api.cast.alicia
    api.script(*(["invoice_ok"] * 3))
    ids = [api.read(alicia) for _ in range(3)]
    monkeypatch.setattr(repository, "LIST_LIMIT", 2)
    rows = api.request("GET", "/api/documents", alicia).json()
    assert [r["id"] for r in rows] == [str(ids[2]), str(ids[1])]
