"""AC-13 · Descartar un documento: pasa a `discarded`, el archivo se borra con el JWT de la persona y se registra el evento."""

import jwt
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from cuadre.documents.storage import StorageDenied, StorageUnavailable
from tests.agents.support import captured_logs
from tests.documents.conftest import Api, db_row


def events(admin: Connection[DictRow], document_id: object) -> list[dict]:
    return admin.execute(
        "select action, metadata from public.activity_log where entity_id = %s order by id", (str(document_id),)
    ).fetchall()


def test_ac13_discarding_a_document_in_review_removes_the_file_and_logs_it(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.read(alicia)
    path = api.path_of(alicia, document_id)
    assert path in api.storage.objects

    response = api.discard(alicia, document_id)
    assert response.status_code == 204 and response.content == b""
    assert db_row(admin, document_id)["status"] == "discarded"
    assert path not in api.storage.objects, "el archivo desaparece de Storage"

    (deletion,) = api.storage.operations("delete")
    claims = jwt.decode(deletion.token, options={"verify_signature": False})
    assert deletion.path == path and claims["sub"] == str(alicia.id), "se borra con el JWT de la persona"

    assert events(admin, document_id)[-1] == {
        "action": "document.discarded",
        "metadata": {"document_id": str(document_id), "from_status": "review"},
    }


def test_ac13_discarding_again_is_409_and_the_document_is_gone_for_the_person(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = api.read(alicia)
    assert api.discard(alicia, document_id).status_code == 204
    again = api.discard(alicia, document_id)
    assert again.status_code == 409 and again.json()["code"] == "document_wrong_state"
    assert api.get(alicia, document_id).status_code == 404
    assert api.preview(alicia, document_id).status_code == 404
    assert api.request("GET", "/api/documents", alicia).json() == []


@pytest.mark.parametrize("state", ["uploading", "extraction_failed"])
def test_a_document_that_is_not_in_review_can_also_be_discarded(api: Api, state: str) -> None:
    alicia = api.cast.alicia
    if state == "uploading":
        document_id = api.uploaded(alicia)
    else:
        api.script(AgentsError(FailureCode.unreadable, http_status=422))
        document_id = api.read(alicia)
    assert api.discard(alicia, document_id).status_code == 204
    assert api.path_of(alicia, document_id) not in api.storage.objects


def test_discarding_a_reservation_whose_file_was_never_uploaded_is_fine(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = api.reserve(alicia).json()["id"]  # no se sube nada
    assert api.discard(alicia, document_id).status_code == 204


@pytest.mark.parametrize("failure", [StorageUnavailable(), StorageDenied()], ids=["no responde", "denegado"])
def test_a_storage_failure_while_deleting_does_not_undo_the_discard(
    api: Api, admin: Connection[DictRow], failure: Exception
) -> None:
    """El estado de la base de datos manda; el archivo huérfano queda para mantenimiento (§4) y se avisa en el registro."""
    alicia = api.cast.alicia
    document_id = api.read(alicia)
    api.storage.fail["delete"] = failure  # type: ignore[assignment]
    with captured_logs("cuadre.documents") as records:
        response = api.discard(alicia, document_id)
    assert response.status_code == 204
    assert db_row(admin, document_id)["status"] == "discarded"
    assert [r.getMessage() for r in records if r.levelname == "WARNING"] == ["storage_delete_failed"]


def test_someone_else_cannot_discard_it_or_delete_the_file(api: Api, admin: Connection[DictRow]) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    document_id = api.read(alicia)
    response = api.discard(beto, document_id)
    assert response.status_code == 404 and response.json()["code"] == "document_not_found"
    assert db_row(admin, document_id)["status"] == "review"
    assert api.path_of(alicia, document_id) in api.storage.objects
    assert api.storage.operations("delete") == []
