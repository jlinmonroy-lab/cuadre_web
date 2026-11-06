"""HttpAgentsClient contra un servidor local guionado (SPEC-W-002 §5.4, AC-03, AC-05, AC-08, T2-04).

Tiempos, conexiones rechazadas, reintentos y cabeceras se prueban de verdad por el cable, no con un transporte simulado.
"""

import contextlib
import json
import time
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from cuadre.agents import AgentsClient, AgentsError, FailureCode, HttpAgentsClient, get_agents_client
from cuadre.agents import http as http_module
from tests.agents.server import Reply, ScriptedServer, closed_port_url
from tests.agents.support import (
    API_KEY,
    SCHEMAS,
    captured_logs,
    example_json,
    example_request,
    make_settings,
    rendered,
    response_json,
    with_extraction,
)

RID = "req-0000001"
OK = response_json("invoice_ok")
UNREADABLE = example_json("unreadable.error.json")


def error_body(code: str) -> dict[str, str]:
    return {"code": code, "message": "texto del agente que no debe llegar a nadie", "trace_id": "trc_err_1"}


def client(server: ScriptedServer, sleeps: list[int] | None = None, **kwargs: Any) -> HttpAgentsClient:
    sleeps = [] if sleeps is None else sleeps
    return HttpAgentsClient(server.url, API_KEY, sleep=sleeps.append, **kwargs)


def extract(c: AgentsClient) -> Any:
    return c.extract_invoice(example_request(), request_id=RID)


def failure(c: AgentsClient) -> AgentsError:
    with pytest.raises(AgentsError) as caught:
        extract(c)
    return caught.value


# --- Lo que sale por el cable (AC-08) ----------------------------------------------------------------------------------------


def test_the_request_is_exactly_what_the_contract_describes(server: ScriptedServer) -> None:
    server.serve(Reply(200, OK))
    extract(client(server))

    (seen,) = server.seen
    assert (seen.method, seen.path) == ("POST", "/v1/extract")
    assert seen.headers["authorization"] == f"Bearer {API_KEY}"
    assert seen.headers["x-cuadre-contract-version"] == "1"
    assert seen.headers["x-request-id"] == RID
    assert seen.headers["content-type"] == "application/json"
    body = json.loads(seen.body)
    assert body == example_json("extract.request.json")
    schema = json.loads((SCHEMAS / "extract_request.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(body)


def test_the_endpoint_is_built_from_the_base_url_with_or_without_a_prefix_and_trailing_slash(
    server: ScriptedServer,
) -> None:
    for base, path in (
        (server.url, "/v1/extract"),
        (server.url + "/", "/v1/extract"),
        (server.url + "/agents/", "/agents/v1/extract"),
    ):
        server.serve(Reply(200, OK))
        extract(HttpAgentsClient(base, API_KEY))
        assert server.seen[0].path == path


def test_ac08_only_the_agents_key_is_ever_sent_never_the_service_key_nor_a_user_token(server: ScriptedServer) -> None:
    service_key = "SERVICE-KEY-DO-NOT-LEAK-0123456789"
    settings = make_settings(
        agents_base_url=server.url,
        agents_api_key=API_KEY,
        supabase_service_role_key=service_key,
        database_service_url="postgresql://cuadre_jobs:DB-PASSWORD-DO-NOT-LEAK@127.0.0.1:5/postgres",
        admin_password="ADMIN-PASSWORD-DO-NOT-LEAK",
    )
    server.serve(Reply(200, OK))
    extract(get_agents_client(settings))

    (seen,) = server.seen
    wire = "\n".join(f"{k}: {v}" for k, v in seen.headers.items()) + "\n" + seen.body.decode()
    for secret in (service_key, "DB-PASSWORD-DO-NOT-LEAK", "ADMIN-PASSWORD-DO-NOT-LEAK"):
        assert secret not in wire
    sent_by_us = set(seen.headers) - {"host", "accept-encoding", "connection", "user-agent", "content-length"}
    assert sent_by_us == {"authorization", "x-cuadre-contract-version", "x-request-id", "content-type", "accept"}


def test_proxies_from_the_environment_are_ignored(server: ScriptedServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """La clave del servicio solo va a la URL configurada, no a un proxy que sugiera el entorno."""
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, closed_port_url())
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    server.serve(Reply(200, OK))
    assert extract(client(server)).trace_id == "trc_synthetic_0001"


# --- Respuestas buenas y malas del servicio ------------------------------------------------------------------------------------


def test_the_unreadable_example_maps_to_unreadable_with_its_trace(server: ScriptedServer) -> None:
    server.serve(Reply(422, UNREADABLE))
    error = failure(client(server))
    assert (error.code, error.http_status, error.trace_id) == (FailureCode.unreadable, 422, "trc_synthetic_0006")
    assert len(server.seen) == 1  # un 4xx nunca se reintenta


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        (Reply(422, error_body("unreadable")), FailureCode.unreadable),
        (Reply(422, error_body("invalid_request")), FailureCode.internal),  # nuestra petición está mal
        (Reply(422, "no es json"), FailureCode.internal),
        (Reply(400, error_body("invalid_request")), FailureCode.internal),
        (Reply(413, error_body("payload_too_large")), FailureCode.payload_too_large),
        (Reply(413, ""), FailureCode.payload_too_large),  # manda el estado, no el cuerpo
        (Reply(415, error_body("unsupported_media_type")), FailureCode.unsupported_media_type),
        (Reply(401, error_body("unauthorized")), FailureCode.agents_unavailable),
        (Reply(403, ""), FailureCode.agents_unavailable),
        (Reply(404, ""), FailureCode.agents_unavailable),
        (Reply(500, error_body("upstream_error")), FailureCode.upstream_error),
        (Reply(503, ""), FailureCode.upstream_error),
        (Reply(429, error_body("upstream_error")), FailureCode.upstream_error),  # sin Retry-After no hay reintento
    ],
    ids=lambda v: f"{v.status}" if isinstance(v, Reply) else v.value,
)
def test_status_mapping_and_no_retry_for_these(server: ScriptedServer, reply: Reply, code: FailureCode) -> None:
    sleeps: list[int] = []
    server.serve(reply)
    error = failure(client(server, sleeps))
    assert error.code is code
    assert error.http_status == reply.status
    assert len(server.seen) == 1 and sleeps == []


def test_the_message_of_the_agent_never_reaches_the_error(server: ScriptedServer) -> None:
    server.serve(Reply(422, error_body("unreadable")))
    error = failure(client(server))
    assert "texto del agente" not in str(error) and "texto del agente" not in repr(error.__dict__)
    assert str(error) == "unreadable"


def test_a_redirect_is_not_followed(server: ScriptedServer) -> None:
    server.serve(Reply(302, "", {"Location": "http://127.0.0.1:9/robar"}))
    error = failure(client(server))
    assert error.code is FailureCode.agents_unavailable
    assert len(server.seen) == 1


# --- Reintentos (AC-05) ------------------------------------------------------------------------------------------------------


def test_ac05_a_single_502_is_retried_once_and_ends_well(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(502, error_body("upstream_error")), Reply(200, OK))
    assert extract(client(server, sleeps)).trace_id == "trc_synthetic_0001"
    assert len(server.seen) == 2 and sleeps == [500]
    assert server.seen[0].headers["x-request-id"] == server.seen[1].headers["x-request-id"] == RID


def test_two_502_in_a_row_are_retried_only_once(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(502, ""), Reply(502, ""), Reply(200, OK))
    error = failure(client(server, sleeps))
    assert error.code is FailureCode.upstream_error
    assert len(server.seen) == 2 and sleeps == [500]
    assert server.script  # el tercero ni se pidió


@pytest.mark.parametrize(
    ("status", "retry_after", "pause"),
    [
        (429, "1", 1000),
        (429, "5", 5000),
        (502, "2", 2000),
        (502, "0", 0),
        (502, None, 500),
        (502, "Wed, 21 Oct 2026 07:28:00 GMT", 500),  # una fecha HTTP no se interpreta: cuenta como ausente
    ],
)
def test_the_retry_pause_follows_retry_after_up_to_five_seconds(
    server: ScriptedServer, status: int, retry_after: str | None, pause: int
) -> None:
    sleeps: list[int] = []
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    server.serve(Reply(status, "", headers), Reply(200, OK))
    extract(client(server, sleeps))
    assert sleeps == [pause] and len(server.seen) == 2


@pytest.mark.parametrize(
    ("status", "retry_after"),
    [(429, None), (429, "6"), (429, "30"), (429, "abc"), (429, "-1"), (429, "1.5"), (502, "6"), (502, "30")],
)
def test_no_retry_when_the_service_asks_for_more_than_five_seconds_or_says_nothing_useful(
    server: ScriptedServer, status: int, retry_after: str | None
) -> None:
    sleeps: list[int] = []
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    server.serve(Reply(status, "", headers), Reply(200, OK))
    error = failure(client(server, sleeps))
    assert error.code is FailureCode.upstream_error
    assert len(server.seen) == 1 and sleeps == []


def test_a_refused_connection_is_retried_once_and_then_the_service_is_unavailable() -> None:
    sleeps: list[int] = []
    c = HttpAgentsClient(closed_port_url(), API_KEY, sleep=sleeps.append)
    error = failure(c)
    assert error.code is FailureCode.agents_unavailable
    assert error.http_status is None
    assert sleeps == [500]


def test_a_timeout_is_never_retried_and_ends_in_time(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(200, OK, delay_ms=2000), Reply(200, OK))
    began = time.monotonic()
    error = failure(client(server, sleeps, timeout_ms=300))
    elapsed = time.monotonic() - began
    assert error.code is FailureCode.timeout
    assert elapsed < 1.5
    assert len(server.seen) == 1 and sleeps == []


def test_the_retry_is_skipped_when_there_is_no_budget_left_for_it(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(502, ""), Reply(200, OK))
    error = failure(client(server, sleeps, timeout_ms=3000))  # tras la pausa quedarían menos de 5 s
    assert error.code is FailureCode.upstream_error
    assert len(server.seen) == 1 and sleeps == []


def test_the_total_budget_also_covers_the_time_between_chunks(server: ScriptedServer) -> None:
    """Si al recibir la respuesta ya no queda presupuesto, es un tiempo agotado aunque el servidor haya contestado."""
    jump = [0]
    server.on_request = lambda: jump.__setitem__(0, 10**12)
    server.serve(Reply(200, OK))
    c = HttpAgentsClient(server.url, API_KEY, timeout_ms=45_000, clock_ns=lambda: time.monotonic_ns() + jump[0])
    assert failure(c).code is FailureCode.timeout


# --- Respuestas inválidas (AC-03) -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"", id="vacío"),
        pytest.param("{no es json", id="json roto"),
        pytest.param(b"\xff\xfe\x00", id="no es utf-8"),
        pytest.param([], id="una lista"),
        pytest.param({}, id="objeto vacío"),
        pytest.param({"extraction": "texto", "usage": {}, "trace_id": "x"}, id="forma errónea"),
        pytest.param(with_extraction("invoice_ok", total="120,5"), id="coma decimal"),
        pytest.param(with_extraction("invoice_ok", total="1e3"), id="notación científica"),
        pytest.param(with_extraction("invoice_ok", total="12.345"), id="tres decimales"),
        pytest.param(with_extraction("invoice_ok", total=120.5), id="número JSON decimal"),
        pytest.param(with_extraction("invoice_ok", total=120), id="número JSON entero"),
        pytest.param(
            with_extraction("invoice_ok", tax_breakdown=[{"vat_rate": 21, "base": "1.00", "vat_amount": "0.21"}]),
            id="tipo numérico",
        ),
        pytest.param(with_extraction("invoice_ok", issue_date=1793491200), id="fecha como entero"),
        pytest.param(with_extraction("invoice_ok", injection_suspected="true"), id="booleano como cadena"),
        pytest.param(with_extraction("invoice_ok", doc_type="invoice_of_the_year"), id="tipo desconocido"),
    ],
)
def test_ac03_an_invalid_body_is_invalid_response_and_is_not_retried(server: ScriptedServer, body: Any) -> None:
    sleeps: list[int] = []
    server.serve(Reply(200, body), Reply(200, OK))
    error = failure(client(server, sleeps))
    assert error.code is FailureCode.invalid_response
    assert len(server.seen) == 1 and sleeps == []
    assert error.__cause__ is None and error.__suppress_context__  # el texto de ValidationError lleva datos recibidos


def padded_valid_body(total_bytes: int) -> bytes:
    """Una respuesta VÁLIDA rellena de espacios hasta `total_bytes` (el JSON admite espacios al final)."""
    text = json.dumps(OK).encode()
    return text + b" " * (total_bytes - len(text))


def test_a_valid_body_over_one_mebibyte_is_rejected_but_exactly_one_mebibyte_is_accepted(
    server: ScriptedServer,
) -> None:
    """El cuerpo es válido en los dos casos: solo el tope de tamaño distingue uno de otro."""
    server.serve(Reply(200, padded_valid_body(http_module.MAX_RESPONSE_BYTES)))
    assert extract(client(server)).trace_id == "trc_synthetic_0001"
    server.serve(Reply(200, padded_valid_body(http_module.MAX_RESPONSE_BYTES + 1)))
    assert failure(client(server)).code is FailureCode.invalid_response


def test_unknown_fields_are_ignored_so_the_contract_can_grow_within_1x(server: ScriptedServer) -> None:
    body = response_json("invoice_ok")
    body["new_top_level_field"] = {"anything": [1, 2, 3]}
    body["extraction"]["new_optional_field"] = "x"
    server.serve(Reply(200, body))
    assert extract(client(server)).extraction.supplier_name == "Nubesoft S.L."


# --- Sin datos sensibles en los registros (T2-04, NFR-11) -----------------------------------------------------------------------


def test_logs_never_contain_the_signed_url_the_key_or_anything_read(server: ScriptedServer) -> None:
    request = example_request()
    forbidden = [
        str(request.document_url),
        "SYNTHETIC-EXAMPLE-TOKEN",
        "token=",
        API_KEY,
        "B00000042",  # NIF del proveedor del fixture
        "Nubesoft",
        "NS-2026-9921",
        "texto del agente",
    ]
    scenarios = [
        Reply(200, OK),
        Reply(200, with_extraction("invoice_ok", total="120,5")),
        Reply(422, error_body("unreadable")),
        Reply(401, error_body("unauthorized")),
        Reply(403, ""),
        Reply(502, error_body("upstream_error")),
        Reply(200, OK, delay_ms=1000),
    ]
    with captured_logs("cuadre", "cuadre.agents") as records:
        for reply in scenarios:
            server.serve(reply, Reply(502, ""))
            with contextlib.suppress(AgentsError):
                c = client(server, timeout_ms=300) if reply.delay_ms else client(server)
                c.extract_invoice(request, request_id=RID)

    text = rendered(records)
    assert records, "el cliente debe registrar lo que hace"
    for needle in forbidden:
        assert needle not in text, f"el registro contiene {needle!r}"
    assert all(getattr(r, "request_id", RID) == RID for r in records)
    outcomes = {getattr(r, "outcome", None) for r in records}
    assert {"ok", "invalid_response", "unreadable", "agents_unavailable", "upstream_error", "timeout"} <= outcomes


def test_a_rejected_key_is_logged_as_a_configuration_error(server: ScriptedServer) -> None:
    server.serve(Reply(401, error_body("unauthorized")))
    with captured_logs("cuadre.agents") as records:
        failure(client(server))
    assert [r.getMessage() for r in records if r.levelname == "ERROR"] == ["agents_auth_rejected"]
