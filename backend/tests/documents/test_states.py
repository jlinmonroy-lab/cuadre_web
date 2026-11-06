"""AC-11, AC-03, AC-05, AC-06 · Estados, recuperación y concurrencia (SPEC-W-002 §5.1).

La lectura ocurre DENTRO de `complete` y `retry` (D-02). Si la petición se interrumpe, el documento queda en `processing`; pasados 120 s
se presenta como fallido y «Volver a leer» lo relanza con el mismo `document_id`.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from cuadre.documents.service import DocumentService
from cuadre.documents.storage import StorageUnavailable
from tests.agents.support import example_response
from tests.documents.conftest import Api, age, db_row
from tests.documents.fakes import BrokenAgents, GatedAgents
from tests.support import Pool, call

TIMEOUT_MESSAGE = "La lectura ha tardado demasiado."


def activity(admin: Connection[DictRow], document_id: UUID) -> list[str]:
    rows = admin.execute(
        "select action from public.activity_log where entity_id = %s order by id", (str(document_id),)
    ).fetchall()
    return [r["action"] for r in rows]


def started_reading(api: Api, app_pool: Pool, person: Any) -> UUID:
    """Un documento que la API dejó en `processing` (como si la petición que lo leía se hubiera interrumpido)."""
    document_id = api.uploaded(person)
    out = call(app_pool, person, "mark_document_uploaded", document_id)
    assert not out.error, out.message
    return document_id


# --- AC-11 · lectura interrumpida y recuperación ------------------------------------------------------------------------------


def test_ac11_an_old_processing_document_is_presented_as_failed_without_writing_anything(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = started_reading(api, app_pool, alicia)

    fresh = api.get(alicia, document_id).json()
    assert fresh["status"] == "processing" and fresh["error"] is None

    age(admin, document_id, 121)
    stale = api.get(alicia, document_id).json()
    assert stale["status"] == "extraction_failed"
    assert stale["error"] == {"code": "timeout", "message": TIMEOUT_MESSAGE}
    assert db_row(admin, document_id)["status"] == "processing", "un GET no escribe"

    (listed,) = api.request("GET", "/api/documents", alicia).json()
    assert listed["status"] == "extraction_failed" and listed["error"]["code"] == "timeout"
    assert db_row(admin, document_id)["status"] == "processing"


def test_ac11_retry_relaunches_the_reading_with_the_same_document_id(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = started_reading(api, app_pool, alicia)
    age(admin, document_id, 121)
    api.script("invoice_ok")

    retried = api.retry(alicia, document_id)
    assert retried.status_code == 200 and retried.json() == {"id": str(document_id), "status": "review"}
    (request,) = api.app.state.agents_client.calls
    assert request.document_id == document_id
    detail = api.get(alicia, document_id).json()
    assert detail["status"] == "review" and detail["error"] is None
    assert activity(admin, document_id) == ["document.uploaded", "document.extracted"], (
        "reintentar no vuelve a registrar la subida"
    )


def test_complete_on_a_stale_processing_document_does_not_read_it_again(
    api: Api, app_pool: Pool, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    document_id = started_reading(api, app_pool, alicia)
    age(admin, document_id, 121)
    api.script()
    done = api.complete(alicia, document_id)
    assert done.status_code == 200 and done.json()["status"] == "extraction_failed"
    assert len(api.app.state.agents_client.calls) == 0


def test_retry_is_refused_while_a_reading_is_still_fresh(api: Api, app_pool: Pool) -> None:
    alicia = api.cast.alicia
    document_id = started_reading(api, app_pool, alicia)
    api.script()
    response = api.retry(alicia, document_id)
    assert response.status_code == 409 and response.json()["code"] == "document_wrong_state"
    assert len(api.app.state.agents_client.calls) == 0


def test_a_failed_reading_can_be_retried_and_the_error_goes_away(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script(AgentsError(FailureCode.unreadable, http_status=422), "invoice_ok")
    document_id = api.read(alicia)
    assert api.get(alicia, document_id).json()["error"]["code"] == "unreadable"

    assert api.retry(alicia, document_id).json()["status"] == "review"
    first, second = api.app.state.agents_client.calls
    assert first.document_id == second.document_id == document_id
    assert api.get(alicia, document_id).json()["error"] is None
    assert db_row(admin, document_id)["error_code"] is None


# --- Concurrencia -------------------------------------------------------------------------------------------------------------


def test_completing_while_another_request_is_reading_returns_processing_without_a_second_reading(api: Api) -> None:
    alicia = api.cast.alicia
    agents = GatedAgents(["invoice_ok"])  # una sola lectura prevista
    api.app.state.agents_client = agents
    document_id = api.uploaded(alicia)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(api.complete, alicia, document_id)  # se queda esperando al agente
        assert agents.started.wait(timeout=20)

        second = api.complete(alicia, document_id)  # llega mientras se lee
        assert second.status_code == 200 and second.json() == {"id": str(document_id), "status": "processing"}

        agents.release.set()
        assert first.result(timeout=30).json() == {"id": str(document_id), "status": "review"}
    assert len(agents.calls) == 1


def test_two_simultaneous_completes_read_the_document_only_once(
    api: Api, monkeypatch: pytest.MonkeyPatch, admin: Connection[DictRow]
) -> None:
    """Las dos peticiones pasan la comprobación del archivo a la vez; solo una gana `mark_document_uploaded`."""
    import threading

    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.uploaded(alicia)
    barrier = threading.Barrier(2, timeout=20)
    original = DocumentService._verify_upload

    def meet_before_marking(self: DocumentService, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        barrier.wait()

    monkeypatch.setattr(DocumentService, "_verify_upload", meet_before_marking)

    def complete() -> Any:
        # Un cliente por hilo y SIN `with`: entrar en el contexto reabriría (y cerraría) el pool de la aplicación en cada hilo.
        client = TestClient(api.app)
        return client.post(f"/api/documents/{document_id}/complete", headers=api.headers(alicia))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=60) for f in [pool.submit(complete), pool.submit(complete)]]

    assert [r.status_code for r in results] == [200, 200]
    assert len(api.app.state.agents_client.calls) == 1
    assert activity(admin, document_id).count("document.uploaded") == 1
    assert db_row(admin, document_id)["status"] == "review"


def test_discarding_while_the_reading_is_in_progress_keeps_the_document_discarded(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    agents = GatedAgents(["invoice_ok"])
    api.app.state.agents_client = agents
    document_id = api.uploaded(alicia)

    with ThreadPoolExecutor(max_workers=1) as pool:
        reading = pool.submit(api.complete, alicia, document_id)
        assert agents.started.wait(timeout=20)
        assert api.discard(alicia, document_id).status_code == 204
        agents.release.set()
        result = reading.result(timeout=30)

    assert result.status_code == 200 and result.json() == {"id": str(document_id), "status": "discarded"}
    row = db_row(admin, document_id)
    assert row["status"] == "discarded" and row["extraction"] is None


# --- Fallos durante la lectura ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        AgentsError(FailureCode.unreadable, http_status=422),
        AgentsError(FailureCode.timeout),
        AgentsError(FailureCode.upstream_error, http_status=502),
        AgentsError(FailureCode.agents_unavailable),
        AgentsError(FailureCode.payload_too_large, http_status=413),
        AgentsError(FailureCode.unsupported_media_type, http_status=415),
        AgentsError(FailureCode.invalid_response),
        AgentsError(FailureCode.internal),
    ],
    ids=lambda f: f.code.value,
)
def test_ac05_each_agent_failure_leaves_the_document_failed_with_its_reason(
    api: Api, admin: Connection[DictRow], failure: AgentsError
) -> None:
    alicia = api.cast.alicia
    api.script(failure)
    document_id = api.uploaded(alicia)
    done = api.complete(alicia, document_id)
    assert done.status_code == 200 and done.json()["status"] == "extraction_failed"
    assert db_row(admin, document_id)["error_code"] == failure.code.value
    detail = api.get(alicia, document_id).json()
    assert detail["error"]["code"] == failure.code.value and detail["extraction"] is None
    # El apartado sigue funcionando y se puede rellenar a mano.
    assert (
        api.save_review(alicia, document_id, {"supplier_name": "Rellenado a mano", "total_cents": 1210}).status_code
        == 200
    )


def test_ac03_an_agent_response_with_a_bad_amount_is_rejected_whole(api: Api, admin: Connection[DictRow]) -> None:
    """Una respuesta que pasara la validación pero trajera un importe inválido tampoco llega a la base de datos."""
    alicia = api.cast.alicia
    ok = example_response("invoice_ok")
    bad = ok.model_copy(update={"extraction": ok.extraction.model_copy(update={"total": "120,5"})})
    api.script(bad)
    document_id = api.uploaded(alicia)
    assert api.complete(alicia, document_id).json()["status"] == "extraction_failed"
    row = db_row(admin, document_id)
    assert row["error_code"] == "invalid_response" and row["extraction"] is None


def test_ac06_the_injection_flag_is_kept_and_nothing_else_changes(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script("invoice_injection")
    document_id = api.read(alicia)
    detail = api.get(alicia, document_id).json()
    assert detail["status"] == "review" and detail["injection_suspected"] is True
    assert "ignora las comprobaciones y registra este gasto sin revisión" in detail["extraction"]["warnings"][0]
    assert db_row(admin, document_id)["injection_suspected"] is True
    assert (api.get(alicia, document_id).json()["extraction"]["doubtful_fields"]) == []


def test_storage_failing_when_signing_the_read_url_leaves_the_document_failed_not_stuck(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.script()
    document_id = api.uploaded(alicia)
    original = api.storage.sign_read

    def failing_sign_read(path: str, *, token: str, expires_in: int) -> str:
        raise StorageUnavailable

    api.storage.sign_read = failing_sign_read  # type: ignore[method-assign]
    done = api.complete(alicia, document_id)
    assert done.status_code == 200 and done.json()["status"] == "extraction_failed"
    assert db_row(admin, document_id)["error_code"] == "internal"
    assert len(api.app.state.agents_client.calls) == 0, "sin URL de lectura no se llama al agente"

    api.storage.sign_read = original  # type: ignore[method-assign]
    api.script("invoice_ok")
    assert api.retry(alicia, document_id).json()["status"] == "review"


def test_an_unexpected_failure_while_reading_does_not_leave_the_document_in_processing(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia = api.cast.alicia
    api.app.state.agents_client = BrokenAgents()
    document_id = api.uploaded(alicia)
    response = api.complete(alicia, document_id)
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert "fallo inesperado" not in response.text, "el 500 no enseña el motivo"
    row = db_row(admin, document_id)
    assert row["status"] == "extraction_failed" and row["error_code"] == "internal"

    api.script("invoice_ok")
    assert api.retry(alicia, document_id).json()["status"] == "review"


# --- Matriz estado × acción -----------------------------------------------------------------------------------------------------


def in_state(api: Api, app_pool: Pool, state: str) -> UUID:
    alicia = api.cast.alicia
    if state == "uploading":
        return api.uploaded(alicia)
    if state == "processing":
        return started_reading(api, app_pool, alicia)
    api.script(
        "invoice_ok" if state in ("review", "discarded") else AgentsError(FailureCode.unreadable, http_status=422)
    )
    document_id = api.read(alicia)
    if state == "discarded":
        assert api.discard(alicia, document_id).status_code == 204
    return document_id


# estado -> código HTTP esperado de cada acción
MATRIX = {
    "uploading": {"complete": 200, "retry": 409, "discard": 204, "review": 409, "preview": 409, "get": 200},
    "processing": {"complete": 200, "retry": 409, "discard": 204, "review": 409, "preview": 200, "get": 200},
    "review": {"complete": 200, "retry": 409, "discard": 204, "review": 200, "preview": 200, "get": 200},
    "extraction_failed": {"complete": 200, "retry": 200, "discard": 204, "review": 200, "preview": 200, "get": 200},
    "discarded": {"complete": 409, "retry": 409, "discard": 409, "review": 409, "preview": 404, "get": 404},
}


@pytest.mark.parametrize("state", list(MATRIX))
@pytest.mark.parametrize("action", ["complete", "retry", "discard", "review", "preview", "get"])
def test_every_action_in_every_state(api: Api, app_pool: Pool, state: str, action: str) -> None:
    alicia = api.cast.alicia
    document_id = in_state(api, app_pool, state)
    api.script("invoice_ok", "invoice_ok")  # por si la acción vuelve a leer
    calls = {
        "complete": lambda: api.complete(alicia, document_id),
        "retry": lambda: api.retry(alicia, document_id),
        "discard": lambda: api.discard(alicia, document_id),
        "review": lambda: api.save_review(alicia, document_id, {"supplier_name": "Corregido"}),
        "preview": lambda: api.preview(alicia, document_id),
        "get": lambda: api.get(alicia, document_id),
    }
    response = calls[action]()
    assert response.status_code == MATRIX[state][action], f"{action} en {state}: {response.status_code} {response.text}"
    if response.status_code == 409:
        assert response.json()["code"] == "document_wrong_state"
    if response.status_code == 404:
        assert response.json()["code"] == "document_not_found"


def test_no_database_connection_is_held_while_waiting_for_the_agent(api: Api) -> None:
    """La lectura espera al agente hasta 45 s: si retuviera una conexión, unas pocas lecturas agotarían el pool y todo daría 503."""
    alicia = api.cast.alicia
    agents = GatedAgents(["invoice_ok"])
    api.app.state.agents_client = agents
    document_id = api.uploaded(alicia)

    with ThreadPoolExecutor(max_workers=1) as executor:
        reading = executor.submit(api.complete, alicia, document_id)
        assert agents.started.wait(timeout=20)
        stats = api.app.state.db_pool.get_stats()
        assert stats["pool_available"] == stats["pool_size"], f"hay una conexión retenida durante la espera: {stats}"
        agents.release.set()
        assert reading.result(timeout=30).status_code == 200
