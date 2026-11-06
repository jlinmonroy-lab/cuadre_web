"""AC-04, T2-08 · Tipo, tamaño, nombre y firma del archivo (SPEC-W-002 §5.1).

Storage no mira el contenido ni cruza la extensión con el tipo (Anexo B.1): lo comprueba la API, y antes de llamar al agente.
"""

from typing import Any
from uuid import UUID

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.documents.limits import MAX_UPLOAD_BYTES, MIME_EXTENSIONS
from cuadre.documents.storage import StorageNotFound, StorageUnavailable
from tests.documents.conftest import PDF, SAMPLES, Api, db_row

MIMES = list(MIME_EXTENSIONS)


def documents_of(admin: Connection[DictRow], person_id: UUID) -> int:
    row = admin.execute("select count(*) as n from public.documents where owner_id = %s", (person_id,)).fetchone()
    assert row is not None
    return int(row["n"])


def problem(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert body["code"] == code and response.headers["content-type"].startswith("application/problem+json")
    return body


def assert_rejected_and_cleaned(
    api: Api, admin: Connection[DictRow], person: Any, document_id: UUID, mime: str = PDF
) -> None:
    """El documento quedó descartado, el archivo se borró con el JWT de la persona y el agente no se llamó."""
    assert db_row(admin, document_id)["status"] == "discarded"
    assert api.path_of(person, document_id, mime) not in api.storage.objects
    (deletion,) = api.storage.operations("delete")
    assert deletion.path == api.path_of(person, document_id, mime)
    assert len(api.app.state.agents_client.calls) == 0


# --- Al reservar: tipo, tamaño y nombre --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mime",
    [
        "text/plain",
        "application/zip",
        "image/gif",
        "image/svg+xml",
        "application/pdf; charset=binary",
        "APPLICATION/PDF",
    ],
)
def test_ac04_a_type_that_is_not_allowed_is_415_and_creates_nothing(
    api: Api, admin: Connection[DictRow], mime: str
) -> None:
    alicia = api.cast.alicia
    problem(api.reserve(alicia, mime=mime, size=100), 415, "unsupported_file_type")
    assert documents_of(admin, alicia.id) == 0
    assert api.storage.calls == []


def test_ac04_a_file_over_15_mib_is_413_and_exactly_15_mib_is_fine(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    problem(api.reserve(alicia, size=MAX_UPLOAD_BYTES + 1), 413, "file_too_large")
    assert documents_of(admin, alicia.id) == 0
    assert api.reserve(alicia, size=MAX_UPLOAD_BYTES).status_code == 201


@pytest.mark.parametrize("size", [0, -1, 12.5, "100", True, None])
def test_a_size_that_is_not_a_positive_integer_is_422(api: Api, admin: Connection[DictRow], size: Any) -> None:
    response = api.request(
        "POST",
        "/api/documents",
        api.cast.alicia,
        json={"filename": "a.pdf", "mime_type": PDF, "size_bytes": size, "source": "file"},
    )
    problem(response, 422, "validation_error")
    assert documents_of(admin, api.cast.alicia.id) == 0


@pytest.mark.parametrize(
    "body",
    [
        {"filename": "", "mime_type": PDF, "size_bytes": 10, "source": "file"},
        {"filename": "\x00\x07\x1b", "mime_type": PDF, "size_bytes": 10, "source": "file"},
        {"filename": "x" * 256, "mime_type": PDF, "size_bytes": 10, "source": "file"},
        {"filename": "a.pdf", "mime_type": PDF, "size_bytes": 10, "source": "email"},
        {"filename": "a.pdf", "mime_type": PDF, "size_bytes": 10},
        {"filename": "a.pdf", "mime_type": PDF, "size_bytes": 10, "source": "file", "storage_path": "x/y.pdf"},
        {"filename": "a.pdf", "mime_type": PDF, "size_bytes": 10, "source": "file", "owner_id": "x"},
        {"filename": "a.pdf", "mime_type": "", "size_bytes": 10, "source": "file"},
    ],
    ids=["vacío", "solo control", "256", "origen", "sin origen", "ruta ajena", "dueño ajeno", "tipo vacío"],
)
def test_malformed_reservations_are_422(api: Api, admin: Connection[DictRow], body: dict[str, Any]) -> None:
    problem(api.request("POST", "/api/documents", api.cast.alicia, json=body), 422, "validation_error")
    assert documents_of(admin, api.cast.alicia.id) == 0


def test_the_file_name_is_only_a_label_it_never_reaches_the_storage_path(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    nasty = "../../etc/pass\x00wd\n.pdf"
    response = api.reserve(alicia, filename=nasty)
    assert response.status_code == 201
    document_id = UUID(response.json()["id"])
    (call,) = api.storage.operations("sign_upload")
    assert call.path == f"{alicia.id}/{document_id}.pdf"  # solo identificadores
    stored = admin.execute("select original_filename from public.documents where id = %s", (document_id,)).fetchone()
    assert stored is not None and "\x00" not in stored["original_filename"] and "\n" not in stored["original_filename"]


@pytest.mark.parametrize("source", ["file", "camera"])
def test_both_sources_are_accepted(api: Api, source: str) -> None:
    assert api.reserve(api.cast.alicia, source=source).status_code == 201


# --- Al completar: existencia, tamaño, tipo registrado y firma -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("declared", "actual"), [(d, a) for d in MIMES for a in MIMES if d != a], ids=lambda m: m.split("/")[1]
)
def test_t208_the_signature_must_be_the_one_of_the_declared_type(
    api: Api, admin: Connection[DictRow], declared: str, actual: str
) -> None:
    alicia = api.cast.alicia
    api.script()  # ninguna lectura prevista: si el agente se llamara, el guion agotado lo delataría
    document_id = api.uploaded(alicia, mime=declared, data=SAMPLES[actual])
    problem(api.complete(alicia, document_id), 422, "file_type_mismatch")
    assert_rejected_and_cleaned(api, admin, alicia, document_id, declared)


@pytest.mark.parametrize("mime", MIMES)
def test_each_type_with_its_own_signature_is_accepted(api: Api, mime: str) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.uploaded(alicia, mime=mime)
    assert api.complete(alicia, document_id).json() == {"id": str(document_id), "status": "review"}


@pytest.mark.parametrize("data", [b"x", b"%PDF", b"\x00" * 40, b"<html>%PDF-</html>"])
def test_a_file_that_is_too_short_or_has_the_signature_in_the_wrong_place_is_rejected(
    api: Api, admin: Connection[DictRow], data: bytes
) -> None:
    alicia = api.cast.alicia
    api.script()
    document_id = api.uploaded(alicia, data=data)
    problem(api.complete(alicia, document_id), 422, "file_type_mismatch")
    assert_rejected_and_cleaned(api, admin, alicia, document_id)


def test_the_type_storage_registered_must_be_the_declared_one(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script()
    document_id = api.uploaded(alicia, registered_type="image/png")  # contenido PDF, pero Storage lo registró como PNG
    problem(api.complete(alicia, document_id), 422, "file_type_mismatch")
    assert_rejected_and_cleaned(api, admin, alicia, document_id)


def test_a_registered_type_with_parameters_and_other_case_is_the_same_type(api: Api) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.uploaded(alicia, registered_type="Application/PDF; charset=binary")
    assert api.complete(alicia, document_id).status_code == 200


def test_the_size_storage_has_must_be_the_declared_one(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script()
    document_id = api.uploaded(alicia, declared_size=len(SAMPLES[PDF]) - 1)
    problem(api.complete(alicia, document_id), 422, "upload_size_mismatch")
    assert_rejected_and_cleaned(api, admin, alicia, document_id)
    assert api.storage.operations("read_head") == [], "con el tamaño mal ni se mira el contenido"


def test_completing_before_the_upload_is_409_and_can_be_repeated(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    reserved = api.reserve(alicia)
    document_id = UUID(reserved.json()["id"])
    problem(api.complete(alicia, document_id), 409, "upload_missing")
    assert db_row(admin, document_id)["status"] == "uploading"

    api.storage.put(api.path_of(alicia, document_id), SAMPLES[PDF], PDF)  # termina la subida
    assert api.complete(alicia, document_id).json()["status"] == "review"


def test_a_file_that_vanishes_between_the_checks_is_upload_missing(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    document_id = api.uploaded(alicia)
    api.storage.fail["read_head"] = StorageNotFound()
    problem(api.complete(alicia, document_id), 409, "upload_missing")
    assert db_row(admin, document_id)["status"] == "uploading"


@pytest.mark.parametrize("operation", ["object_info", "read_head"])
def test_storage_being_down_is_503_with_retry_after_and_the_document_stays_uploading(
    api: Api, admin: Connection[DictRow], operation: str
) -> None:
    alicia = api.cast.alicia
    document_id = api.uploaded(alicia)
    api.storage.fail[operation] = StorageUnavailable()
    response = api.complete(alicia, document_id)
    problem(response, 503, "storage_unavailable")
    assert response.headers["retry-after"] == "5"
    assert db_row(admin, document_id)["status"] == "uploading"
    del api.storage.fail[operation]
    api.script("invoice_ok")
    assert api.complete(alicia, document_id).status_code == 200  # y se puede reintentar


def test_storage_being_down_when_signing_the_upload_discards_the_reservation(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.storage.fail["sign_upload"] = StorageUnavailable()
    response = api.reserve(alicia)
    problem(response, 503, "storage_unavailable")
    assert response.headers["retry-after"] == "5"
    rows = admin.execute(
        "select status::text as status from public.documents where owner_id = %s", (alicia.id,)
    ).fetchall()
    assert [r["status"] for r in rows] == ["discarded"]  # no queda una reserva huérfana en `uploading`


def test_the_original_file_name_plays_no_part_in_deciding_the_type(api: Api) -> None:
    """Un nombre acabado en `.exe` no importa: manda el tipo declarado y la firma del contenido."""
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.uploaded(alicia, filename="no-es-un-pdf.exe")
    assert api.complete(alicia, document_id).status_code == 200
    assert api.get(alicia, document_id).json()["original_filename"] == "no-es-un-pdf.exe"
