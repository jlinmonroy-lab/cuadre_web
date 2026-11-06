"""AC-01, T2-09, T2-10 · Subida y lectura de una factura (SPEC-W-002 §5.1)."""

import time
from uuid import UUID

import jwt
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import AgentsError, FailureCode
from cuadre.documents.limits import MAX_UPLOAD_BYTES
from tests.agents.support import example_response
from tests.documents.conftest import FILENAME, PDF, SAMPLES, Api, db_row
from tests.documents.fakes import SpyAgents


def activity(admin: Connection[DictRow], document_id: UUID) -> list[dict]:
    return admin.execute(
        "select action, metadata from public.activity_log where entity_id = %s order by id",
        (str(document_id),),
    ).fetchall()


def test_ac01_reserve_upload_complete_and_review(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia

    reserved = api.reserve(alicia)
    assert reserved.status_code == 201, reserved.text
    body = reserved.json()
    document_id = UUID(body["id"])
    assert set(body) == {"id", "status", "upload", "max_bytes"}
    assert body["status"] == "uploading" and body["max_bytes"] == MAX_UPLOAD_BYTES
    assert body["upload"]["method"] == "PUT"
    assert body["upload"]["headers"] == {"Content-Type": PDF}
    assert body["upload"]["url"].startswith("https://storage.test/") and "token=" in body["upload"]["url"]
    assert db_row(admin, document_id)["status"] == "uploading"

    api.storage.put(api.path_of(alicia, document_id), SAMPLES[PDF], PDF)
    api.script("invoice_ok")
    done = api.complete(alicia, document_id)
    assert done.status_code == 200, done.text
    assert done.json() == {"id": str(document_id), "status": "review"}

    detail = api.get(alicia, document_id).json()
    assert detail["status"] == "review" and detail["error"] is None
    assert detail["original_filename"] == FILENAME and detail["mime_type"] == PDF and detail["source"] == "file"
    extraction = detail["extraction"]
    assert extraction["supplier_name"] == "Nubesoft S.L." and extraction["total_cents"] == 3000
    assert extraction["tax_breakdown"] == [{"vat_rate": "21", "base_cents": 2479, "vat_cents": 521}]
    assert detail["review"] is None and detail["injection_suspected"] is False
    assert "storage_path" not in detail and "agent_trace_id" not in detail and "agent_cost_eur" not in detail

    events = activity(admin, document_id)
    assert [e["action"] for e in events] == ["document.uploaded", "document.extracted"]
    assert events[0]["metadata"] == {
        "document_id": str(document_id),
        "mime_type": PDF,
        "size_bytes": len(SAMPLES[PDF]),
        "source": "file",
    }
    assert events[1]["metadata"] == {"document_id": str(document_id), "injection_suspected": False, "doubtful_count": 0}
    for event in events:
        flat = str(event["metadata"])
        assert FILENAME not in flat and "B00000042" not in flat and "3000" not in flat


def test_the_list_shows_what_the_screen_needs_and_hides_unfinished_and_discarded_documents(api: Api) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    api.script(
        "invoice_doubtful_nif", "invoice_injection", AgentsError(FailureCode.unreadable, http_status=422), "invoice_ok"
    )
    doubtful = api.read(alicia)
    injected = api.read(alicia)
    unreadable = api.read(alicia)
    api.uploaded(alicia)  # sigue en `uploading`: no sale
    discarded = api.read(alicia)
    assert api.discard(alicia, discarded).status_code == 204  # descartado: no sale

    rows = api.request("GET", "/api/documents", alicia).json()
    assert [r["id"] for r in rows] == [str(unreadable), str(injected), str(doubtful)]  # del más reciente al más antiguo
    failed, with_injection, with_doubt = rows
    assert failed["status"] == "extraction_failed" and failed["error"]["code"] == "unreadable"
    assert failed["supplier_name"] is None and failed["total_cents"] is None and failed["doubtful_count"] == 0
    assert with_injection["injection_suspected"] is True and with_injection["error"] is None
    assert with_doubt == {
        "id": str(doubtful),
        "status": "review",
        "original_filename": FILENAME,
        "mime_type": PDF,
        "created_at": with_doubt["created_at"],
        "doc_type": "full_invoice",
        "supplier_name": "Imprenta Sol S.L.",
        "total_cents": 14520,
        "doubtful_count": 1,
        "injection_suspected": False,
        "error": None,
    }
    assert api.request("GET", "/api/documents", beto).json() == []


@pytest.mark.parametrize("repeats", [1, 3])
def test_t209_completing_again_never_launches_another_reading(api: Api, repeats: int) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")  # un guion de UNA lectura: una segunda lectura haría fallar (FakeScriptExhausted)
    document_id = api.uploaded(alicia)
    assert api.complete(alicia, document_id).json()["status"] == "review"
    for _ in range(repeats):
        again = api.complete(alicia, document_id)
        assert again.status_code == 200 and again.json() == {"id": str(document_id), "status": "review"}
    assert len(api.app.state.agents_client.calls) == 1


def test_a_failed_reading_is_reported_not_raised(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script(AgentsError(FailureCode.upstream_error, http_status=502))
    document_id = api.uploaded(alicia)
    done = api.complete(alicia, document_id)
    assert done.status_code == 200 and done.json()["status"] == "extraction_failed"
    detail = api.get(alicia, document_id).json()
    assert detail["error"] == {
        "code": "upstream_error",
        "message": "El servicio de lectura no está disponible ahora. Puedes reintentarlo o rellenar los datos a mano.",
    }
    assert [e["action"] for e in activity(admin, document_id)] == ["document.uploaded", "document.extraction_failed"]


def test_the_reading_receives_a_short_lived_signed_url_made_with_the_users_jwt(api: Api) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.uploaded(alicia)
    api.complete(alicia, document_id)

    (request,) = api.app.state.agents_client.calls
    assert request.document_id == document_id and str(request.mime_type.value) == PDF
    assert api.storage.read_expiries == [120]
    assert str(request.document_url) == api.storage.signed_urls[-1]


def test_storage_is_always_called_with_the_jwt_of_the_person(api: Api) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.uploaded(alicia)
    api.complete(alicia, document_id)
    api.preview(alicia, document_id)
    api.discard(alicia, document_id)

    assert api.storage.calls, "debería haber llamado a Storage"
    # El JWT no se guarda entero (cada petición firma uno nuevo): lo que importa es que viaja el de la persona y nunca otro.
    for call in api.storage.calls:
        claims = jwt.decode(call.token, options={"verify_signature": False})
        assert claims["sub"] == str(alicia.id) and claims["role"] == "authenticated"
    assert {"sign_upload", "object_info", "read_head", "sign_read", "delete"} == {
        c.operation for c in api.storage.calls
    }


def test_t210_the_web_adds_no_noticeable_latency(api: Api) -> None:
    """Con el agente simulado, de «completar» a «Para revisar» pasa menos de 3 s (NFR-01 es del agente, no de la web)."""
    alicia = api.cast.alicia
    document_id = api.uploaded(alicia)
    began = time.monotonic()
    done = api.complete(alicia, document_id)
    elapsed = time.monotonic() - began
    assert done.json()["status"] in {"review", "extraction_failed"}
    assert elapsed < 3, f"complete tardó {elapsed:.2f} s"


def test_every_document_type_goes_through_the_whole_flow(api: Api) -> None:
    alicia = api.cast.alicia
    api.script(*(["invoice_ok"] * len(SAMPLES)))
    for mime in SAMPLES:
        document_id = api.read(alicia, mime=mime)
        assert api.get(alicia, document_id).json()["mime_type"] == mime
        assert api.storage.objects[api.path_of(alicia, document_id, mime)][1] == mime


def test_the_example_extraction_is_stored_in_cents_only(api: Api, admin: Connection[DictRow]) -> None:
    alicia = api.cast.alicia
    api.script(example_response("invoice_sum_mismatch"))
    document_id = api.read(alicia)
    stored = db_row(admin, document_id)["extraction"]
    assert stored["total_cents"] == 14700 and isinstance(stored["total_cents"], int)
    assert all(isinstance(v, int) for line in stored["tax_breakdown"] for v in (line["base_cents"], line["vat_cents"]))


def test_the_request_id_of_the_request_travels_to_the_agent(api: Api) -> None:
    """El mismo `X-Request-Id` que ve la persona en la respuesta es el que recibe el servicio de agentes (trazabilidad entre repositorios)."""
    alicia = api.cast.alicia
    spy = SpyAgents(["invoice_ok"])
    api.app.state.agents_client = spy
    first = api.uploaded(alicia)
    response = api.complete(alicia, first)
    assert spy.request_ids == [response.headers["x-request-id"]]


@pytest.mark.parametrize(("mime", "previewable"), [(PDF, True), ("image/jpeg", True), ("image/heic", False)])
def test_the_preview_is_a_signed_url_of_60_seconds_and_heic_is_download_only(
    api: Api, mime: str, previewable: bool
) -> None:
    alicia = api.cast.alicia
    api.script("invoice_ok")
    document_id = api.read(alicia, mime=mime)
    api.storage.read_expiries.clear()

    response = api.preview(alicia, document_id)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"url", "expires_in", "previewable"}
    assert body["expires_in"] == 60 and body["previewable"] is previewable
    assert api.storage.read_expiries == [60], "a Storage se le pide una URL de 60 s, no de más"
    assert body["url"] == api.storage.signed_urls[-1]
