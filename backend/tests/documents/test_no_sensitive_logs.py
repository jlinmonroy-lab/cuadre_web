"""AC-09, T2-04, NFR-11 · Ni URLs firmadas, ni tokens, ni nombres de archivo, ni datos del documento en los registros.

Se recorre el flujo completo (subida, lectura buena, lectura fallida y reintento, firma falsa, corrección, vista previa, descarte con
fallo de borrado, errores de la API y un fallo inesperado) con todos los registros de la aplicación capturados.
"""

import logging

from cuadre.agents import AgentsError, FailureCode
from cuadre.documents.storage import StorageUnavailable
from tests.agents.support import captured_logs, example_response, rendered
from tests.documents.conftest import FILENAME, Api
from tests.documents.fakes import BrokenAgents

# Datos del fixture `invoice_ok` y de la corrección: ninguno puede salir.
SENSITIVE_DATA = ["B00000042", "Nubesoft", "NS-2026-9921", "12345678Z", "B00000075", "Corregido SL", "99999", "30.00"]


def test_ac09_nothing_sensitive_reaches_the_logs(api: Api) -> None:
    alicia, gina = api.cast.alicia, api.cast.gina
    api.script(
        "invoice_ok",
        AgentsError(FailureCode.upstream_error, http_status=502, trace_id="trc_secret_trace"),
        example_response("invoice_doubtful_nif"),
    )

    with captured_logs("cuadre") as records:
        good = api.read(alicia)
        api.get(alicia, good)
        api.request("GET", "/api/documents", alicia)
        api.preview(alicia, good)
        api.save_review(
            alicia, good, {"supplier_name": "Corregido SL", "supplier_tax_id": "B00000075", "total_cents": 99999}
        )

        failed = api.read(alicia)  # el agente falla
        api.retry(alicia, failed)  # y el reintento sale bien

        forged = api.uploaded(alicia, data=b"esto no es un pdf")  # firma falsa -> descartado
        api.complete(alicia, forged)
        api.complete(alicia, good)  # idempotente

        api.storage.fail["delete"] = StorageUnavailable()
        api.discard(alicia, good)  # el borrado del archivo falla: se avisa, sin datos

        api.get(alicia, "00000000-0000-4000-8000-000000000000")  # 404
        api.request("GET", "/api/documents", gina)  # 403
        api.client.get("/api/documents")  # 401
        api.reserve(alicia, mime="text/plain", size=10, filename=FILENAME)  # 415
        api.save_review(alicia, failed, {"total_cents": 12.5})  # 422

        api.app.state.agents_client = BrokenAgents()
        broken = api.uploaded(alicia)
        assert api.complete(alicia, broken).status_code == 500  # fallo inesperado

    assert records, "debería haber registros de las peticiones"
    text = rendered(records)
    tokens = {call.token for call in api.storage.calls}
    forbidden = [
        FILENAME,
        "factura-privada",
        "token=",
        "SIGNED-",
        "trc_secret_trace",
        "Bearer",
        "Authorization",
        *api.storage.signed_urls,
        *(part for token in tokens for part in token.split(".")),
        *SENSITIVE_DATA,
    ]
    for needle in forbidden:
        assert needle not in text, f"el registro contiene {needle!r}"


def test_the_request_log_has_the_route_template_the_status_and_who_but_nothing_more(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = api.read(alicia)
    with captured_logs("cuadre.request") as records:
        api.get(alicia, document_id)
    (record,) = records
    assert record.route == "/api/documents/{document_id}"  # type: ignore[attr-defined]
    assert record.status == 200 and record.user_id == str(alicia.id)  # type: ignore[attr-defined]
    assert str(document_id) not in rendered(records), "la plantilla de la ruta, no la ruta con el identificador"


def test_the_http_libraries_never_log_requests() -> None:
    """`httpx2` registra en INFO cada URL completa; la aplicación los deja en WARNING sea cual sea el entorno."""
    for name in ("httpx2", "httpcore2"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING, name
