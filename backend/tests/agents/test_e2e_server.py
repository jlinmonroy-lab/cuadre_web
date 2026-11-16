"""El servidor de agentes del E2E (`e2e_server.py`) se porta como el real: un E2E que dependa de él solo vale si él es fiel.

Servidor de verdad en un puerto efímero, un `ScriptedServer` haciendo de Storage (la URL firmada del documento) y `HttpAgentsClient`
como cliente: lo mismo que recorrerá la API en el E2E.
"""

import json
import time
from collections.abc import Iterator
from threading import Thread
from uuid import uuid4

import httpx2 as httpx
import pytest

from cuadre.agents.errors import AgentsError, FailureCode
from cuadre.agents.fake import FakeAgentsClient
from cuadre.agents.http import HttpAgentsClient
from cuadre.agents.sse import frames_of
from cuadre_contracts import ChatRequest, ExtractRequest
from cuadre_contracts.extract import MimeType
from tests.agents.e2e_server import (
    E2E_CHAT_FIXTURES,
    HOSTILE_WORD,
    MAX_DELAY_MS,
    MAX_PACE_MS,
    AgentsServer,
    ChatMarker,
    Marker,
    chat_reply,
    encode_frame,
    fixture_reply,
    parse_chat_marker,
    parse_marker,
)
from tests.agents.server import Reply, ScriptedServer, closed_port_url
from tests.agents.support import (
    API_KEY,
    CHAT_NAMES,
    RESPONSE_NAMES,
    chat_request,
    drain_frames,
    event_names,
    example_path,
)


@pytest.fixture
def double() -> Iterator[AgentsServer]:
    srv = AgentsServer(0, API_KEY)
    Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def request_for(storage: ScriptedServer, *, document_id: str | None = None, path: str = "/file") -> ExtractRequest:
    return ExtractRequest.model_validate(
        {
            "document_id": document_id or str(uuid4()),
            "document_url": f"{storage.url}{path}",
            "mime_type": MimeType.pdf,
            "locale": "es-ES",
        }
    )


def read(double: AgentsServer, request: ExtractRequest, *, key: str = API_KEY):
    return HttpAgentsClient(double.url, key).extract_invoice(request, request_id="req-e2e")


def post(double: AgentsServer, request: ExtractRequest, **headers: str) -> httpx.Response:
    base = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Cuadre-Contract-Version": "1",
        "X-Request-Id": "req-e2e",
        "Content-Type": "application/json",
    }
    base.update(headers)
    return httpx.post(f"{double.url}/v1/extract", content=request.model_dump_json(), headers=base, timeout=10)


def pdf_with(marker: str) -> bytes:
    """Un archivo con el marcador entre corchetes dobles, como lo escribe `frontend/e2e/helpers/files.ts`."""
    return f"%PDF-1.4\n%[[{marker}]]\n%%EOF\n".encode()


# --- El marcador ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"%PDF-1.4\n%[[fixture:invoice_ok]]\n", Marker(("invoice_ok",), 0)),
        (b"xx [[fixture:unreadable>invoice_ok]] yy", Marker(("unreadable", "invoice_ok"), 0)),
        (b"[[fixture:invoice_ok;delay=2500]]", Marker(("invoice_ok",), 2500)),
        (b"[[fixture:a>b>c;delay=1]]", Marker(("a", "b", "c"), 1)),
        (b"[[fixture:invoice_ok;delay=999999]]", Marker(("invoice_ok",), MAX_DELAY_MS)),  # tope: 10 s
        (b"[[fixture:invoice_ok]] [[fixture:invoice_injection]]", Marker(("invoice_ok",), 0)),  # manda el primero
        (b"Comment\x00[[fixture:ticket_simplified]]\x00", Marker(("ticket_simplified",), 0)),  # en un trozo tEXt de PNG
    ],
)
def test_the_marker_is_found_inside_the_file(data: bytes, expected: Marker) -> None:
    assert parse_marker(data) == expected


@pytest.mark.parametrize("crc_start", [b"q", b"a", b"z", b"_", b"\x00", b"\xab"])
def test_the_bytes_that_follow_the_marker_never_become_part_of_the_name(crc_start: bytes) -> None:
    # En un PNG, los 4 bytes del CRC del trozo `tEXt` van pegados al texto: sin un cierre explícito, una letra minúscula como
    # primer byte del CRC se pegaría al nombre y nombraría un ejemplo que no existe (le pasó al primer intento del E2E).
    data = b"Comment\x00[[fixture:invoice_doubtful_nif]]" + crc_start + b"\x12\xcd"
    assert parse_marker(data) == Marker(("invoice_doubtful_nif",), 0)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"%PDF-1.4 sin marcador",
        b"fixture:invoice_ok",  # sin corchetes no es un marcador: podría pegarse a lo que venga detrás
        b"[[fixture:invoice_ok",
        b"[[fixture:invoice_ok]",
        b"[[fixture:]]",
        b"[[fixture:>a]]",
        b"[[fixture:Invoice_ok]]",
        b"[[FIXTURE:invoice_ok]]",
    ],
)
def test_a_file_without_a_valid_marker_has_none(data: bytes) -> None:
    assert parse_marker(data) is None


def test_the_name_is_read_whole_so_a_longer_name_is_another_example() -> None:
    assert parse_marker(b"[[fixture:invoice_okq]]") == Marker(("invoice_okq",), 0)
    assert fixture_reply("invoice_okq") is None  # no se confunde con `invoice_ok`


def test_every_contract_example_can_be_served_and_unknown_ones_cannot() -> None:
    for name in RESPONSE_NAMES:
        assert fixture_reply(name) == (200, example_path(f"{name}.response.json").read_bytes())
    status, body = fixture_reply("unreadable") or (0, b"")
    assert status == 422 and body == example_path("unreadable.error.json").read_bytes()
    assert fixture_reply("no_existe") is None
    assert fixture_reply("../extract.request") is None  # sin caracteres de ruta: el marcador ni siquiera los admite


# --- Lo que lee la API: lo mismo que el simulado --------------------------------------------------------------------------


@pytest.mark.parametrize("name", RESPONSE_NAMES)
def test_http_client_gets_what_the_fake_client_would_for_every_example(
    name: str, double: AgentsServer, server: ScriptedServer
) -> None:
    server.serve(Reply(200, pdf_with(f"fixture:{name}")))
    request = request_for(server)
    assert read(double, request) == FakeAgentsClient(script=[name]).extract_invoice(request, request_id="req-e2e")


def test_the_unreadable_example_fails_like_the_fake_client_does(double: AgentsServer, server: ScriptedServer) -> None:
    server.serve(Reply(200, pdf_with("fixture:unreadable")))
    with pytest.raises(AgentsError) as caught:
        read(double, request_for(server))
    assert caught.value.code is FailureCode.unreadable and caught.value.http_status == 422


def test_the_agent_downloads_the_signed_url_anonymously(double: AgentsServer, server: ScriptedServer) -> None:
    server.serve(Reply(200, pdf_with("fixture:invoice_ok")))
    read(double, request_for(server, path="/object/sign/documents/u/d.pdf?token=SYNTHETIC"))
    [seen] = server.seen
    assert seen.method == "GET" and seen.path == "/object/sign/documents/u/d.pdf?token=SYNTHETIC"
    assert "authorization" not in seen.headers and "apikey" not in seen.headers and "cookie" not in seen.headers


# --- Varias lecturas del mismo documento ----------------------------------------------------------------------------------


def test_a_sequence_changes_with_each_read_of_the_same_document_only(
    double: AgentsServer, server: ScriptedServer
) -> None:
    body = pdf_with("fixture:unreadable>invoice_ok")
    document = str(uuid4())
    server.serve(*[Reply(200, body)] * 3)
    with pytest.raises(AgentsError):
        read(double, request_for(server, document_id=document))  # 1.ª: unreadable
    assert read(double, request_for(server, document_id=document)).extraction.supplier_name == "Nubesoft S.L."  # 2.ª
    assert read(double, request_for(server, document_id=document)).extraction.supplier_name == "Nubesoft S.L."  # repite

    server.serve(Reply(200, body))
    with pytest.raises(AgentsError):  # otro documento empieza de cero
        read(double, request_for(server))


def test_the_delay_is_honoured(double: AgentsServer, server: ScriptedServer) -> None:
    server.serve(Reply(200, pdf_with("fixture:invoice_ok;delay=400")))
    started = time.monotonic()
    read(double, request_for(server))
    assert time.monotonic() - started >= 0.4


# --- Se porta como el agente real -----------------------------------------------------------------------------------------


def test_a_file_without_a_marker_is_the_tests_fault_not_an_unreadable_document(
    double: AgentsServer, server: ScriptedServer
) -> None:
    server.serve(Reply(200, b"%PDF-1.4\n%sin marcador\n"))
    with pytest.raises(AgentsError) as caught:
        read(double, request_for(server))
    assert caught.value.code is FailureCode.internal and caught.value.http_status == 400


def test_an_unknown_example_in_the_marker_is_a_client_error(double: AgentsServer, server: ScriptedServer) -> None:
    server.serve(Reply(200, pdf_with("fixture:no_existe")))
    assert post(double, request_for(server)).status_code == 400


def test_the_key_the_contract_version_and_the_request_id_are_required(
    double: AgentsServer, server: ScriptedServer
) -> None:
    request = request_for(server)
    server.serve(*[Reply(200, pdf_with("fixture:invoice_ok"))] * 8)
    assert post(double, request).status_code == 200
    assert post(double, request, Authorization="Bearer otra-clave").status_code == 401
    assert post(double, request, Authorization="").status_code == 401
    assert post(double, request, **{"X-Cuadre-Contract-Version": "2"}).status_code == 400
    assert post(double, request, **{"X-Cuadre-Contract-Version": ""}).status_code == 400
    assert post(double, request, **{"X-Request-Id": ""}).status_code == 400
    with pytest.raises(AgentsError) as caught:
        read(double, request, key="otra-clave")
    assert caught.value.http_status == 401


def test_a_body_that_breaks_the_contract_is_rejected(double: AgentsServer) -> None:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Cuadre-Contract-Version": "1",
        "X-Request-Id": "r",
        "Content-Type": "application/json",
    }
    bodies = (
        b"",
        b"no es json",
        b'{"document_id": "no-uuid"}',
        b'{"document_id": "%s", "mime_type": "application/pdf"}' % str(uuid4()).encode(),
    )
    for body in bodies:
        assert httpx.post(f"{double.url}/v1/extract", content=body, headers=headers, timeout=10).status_code == 400


def test_a_document_that_cannot_be_downloaded_is_an_upstream_error(
    double: AgentsServer, server: ScriptedServer
) -> None:
    server.serve(Reply(404, b"no existe"))
    assert post(double, request_for(server)).status_code == 502
    gone = ExtractRequest.model_validate(
        {
            "document_id": str(uuid4()),
            "document_url": f"{closed_port_url()}/file",
            "mime_type": "application/pdf",
            "locale": "es-ES",
        }
    )
    assert post(double, gone).status_code == 502


def test_healthz_and_unknown_paths(double: AgentsServer) -> None:
    assert httpx.get(f"{double.url}/healthz", timeout=10).json() == {"status": "ok"}
    assert httpx.get(f"{double.url}/otra", timeout=10).status_code == 404
    assert httpx.post(f"{double.url}/v1/otra", content=b"{}", timeout=10).status_code == 404


def test_a_busy_port_is_an_error_and_not_a_second_listener(double: AgentsServer) -> None:
    # En Windows, con `SO_REUSEADDR`, esto se enlazaba sin error y las peticiones iban al proceso que no era.
    with pytest.raises(OSError):
        AgentsServer(double.server_address[1], API_KEY)


def test_it_writes_nothing_about_the_document_or_its_url(
    double: AgentsServer, server: ScriptedServer, capfd: pytest.CaptureFixture[str]
) -> None:
    server.serve(Reply(200, pdf_with("fixture:invoice_ok")))
    read(double, request_for(server, path="/object/sign/documents/u/d.pdf?token=SECRETO-DE-PRUEBA"))
    out, err = capfd.readouterr()
    assert "SECRETO-DE-PRUEBA" not in out + err and "fixture:" not in out + err and "Nubesoft" not in out + err


# --- Chat (SPEC-W-004 hito 6) ---------------------------------------------------------------------------------------------

CHAT_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "X-Cuadre-Contract-Version": "1",
    "X-Request-Id": "req-e2e",
    "Content-Type": "application/json",
}


def say(text: str, *, conversation: str | None = None, tools: bool = False) -> ChatRequest:
    base = chat_request("chat" if tools else "chat_no_tools").model_dump(mode="json")
    base["messages"] = [{"role": "user", "content": text}]
    if conversation is not None:
        base["conversation_id"] = conversation
    return ChatRequest.model_validate(base)


def ask(double: AgentsServer, text: str, *, conversation: str | None = None):
    return drain_frames(
        HttpAgentsClient(double.url, API_KEY).stream_chat(say(text, conversation=conversation), request_id="req-e2e")
    )


def post_chat(double: AgentsServer, body: bytes | None = None, **headers: str) -> httpx.Response:
    payload = say("[fixture:answer_with_citation]").model_dump_json().encode() if body is None else body
    return httpx.post(f"{double.url}/v1/chat", content=payload, headers={**CHAT_HEADERS, **headers}, timeout=10)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hola [fixture:answer_with_citation]", ChatMarker("answer_with_citation", None, 0)),
        ("[fixture:a][then:b]", ChatMarker("a", "b", 0)),
        ("[fixture:a][then:b][pace=300]", ChatMarker("a", "b", 300)),
        ("[pace=250][fixture:a]", ChatMarker("a", None, 250)),  # el orden da igual
        ("[fixture:a][pace=99999]", ChatMarker("a", None, MAX_PACE_MS)),  # tope: 5 s por frame
        ("[fixture:a][fixture:b]", ChatMarker("a", None, 0)),  # manda el primero
        ("[fixture:a][pace=1][pace=2]", ChatMarker("a", None, 1)),
    ],
)
def test_the_chat_marker_is_read_from_the_message(text: str, expected: ChatMarker) -> None:
    assert parse_chat_marker(text) == expected


@pytest.mark.parametrize(
    "text", ["sin marcador", "[pace=300]", "[then:b]", "[fixture:A]", "[fixture:]", "[fixture:a;pace=1"]
)
def test_a_message_without_a_valid_fixture_marker_has_none(text: str) -> None:
    assert parse_chat_marker(text) is None


def test_the_e2e_fixtures_do_not_hide_a_contract_example_and_unknown_names_do_not_exist() -> None:
    assert not set(E2E_CHAT_FIXTURES) & set(CHAT_NAMES)
    assert chat_reply("no_existe") is None
    assert chat_reply("../chat.request") is None and chat_reply("chat.request") is None


def test_the_hostile_fixture_is_a_valid_stream_with_the_content_the_screen_must_not_trust() -> None:
    events = chat_reply("hostile")
    assert isinstance(events, list)
    frames = frames_of(b"".join(events))  # el mismo lector que la API: solo pasa si cumple el contrato
    assert event_names(frames) == ["token", "token", "citation", "done"]
    assert [encode_frame(frame) for frame in frames] == events  # lo que se escribe es lo que se leería
    text = "".join(f.root.data.delta for f in frames if f.root.event == "token")
    assert (
        "<img" in text
        and "<script>" in text
        and "**negrita**" in text
        and "javascript:" in text
        and HOSTILE_WORD in text
    )
    citation = next(f.root.data for f in frames if f.root.event == "citation")
    assert str(citation.url).startswith("http://")  # `http:`: no se convierte en enlace


def test_the_unavailable_fixture_fails_before_the_first_frame() -> None:
    status, body = chat_reply("http_unavailable") or (0, b"")
    assert status == 503 and json.loads(body)["code"] == "upstream_error"
    assert status not in (429, 502)  # el cliente solo reintenta esos: el contador de turnos no se descuadra


@pytest.mark.parametrize("name", CHAT_NAMES)
def test_http_client_gets_what_the_fake_client_would_for_every_chat_example(name: str, double: AgentsServer) -> None:
    got, error = ask(double, f"hola [fixture:{name}]")
    expected, _ = drain_frames(FakeAgentsClient().stream_chat(say(f"hola [fixture:{name}]"), request_id="req-e2e"))
    assert error is None
    assert [f.model_dump_json() for f in got] == [f.model_dump_json() for f in expected]


def test_the_hostile_fixture_reaches_the_client_as_the_frames_it_was_built_from(double: AgentsServer) -> None:
    got, error = ask(double, "[fixture:hostile]")
    assert error is None
    assert [encode_frame(f) for f in got] == chat_reply("hostile")


def test_a_failure_before_the_first_frame_is_one_unretried_agent_error(double: AgentsServer) -> None:
    conversation = str(uuid4())
    got, error = ask(double, "[fixture:http_unavailable]", conversation=conversation)
    assert got == [] and isinstance(error, AgentsError)
    assert error.code is FailureCode.upstream_error and error.http_status == 503
    assert double.next_chat_turn(conversation) == 1  # una sola petición: sin reintento


def test_then_changes_the_answer_from_the_second_request_of_that_conversation_only(double: AgentsServer) -> None:
    text = "[fixture:http_unavailable][then:answer_with_citation]"
    conversation = str(uuid4())
    got, error = ask(double, text, conversation=conversation)
    assert got == [] and isinstance(error, AgentsError)  # 1.ª: falla
    for _ in range(2):  # 2.ª y siguientes: responde
        got, error = ask(double, text, conversation=conversation)
        assert error is None and event_names(got)[-1] == "done"
    got, error = ask(double, text)  # otra conversación empieza de cero
    assert got == [] and isinstance(error, AgentsError)


def test_without_then_every_request_gets_the_same_answer(double: AgentsServer) -> None:
    conversation = str(uuid4())
    for _ in range(3):
        got, error = ask(double, "[fixture:abstention_professional]", conversation=conversation)
        assert error is None and "abstention" in event_names(got)


def test_the_pace_waits_before_every_frame_including_the_first(double: AgentsServer) -> None:
    started = time.monotonic()
    arrivals: list[float] = []
    body = say("[fixture:answer_with_citation][pace=150]").model_dump_json()
    with httpx.stream("POST", f"{double.url}/v1/chat", content=body, headers=CHAT_HEADERS, timeout=10) as response:
        assert response.status_code == 200 and response.headers["content-type"] == "text/event-stream"
        assert response.headers["cache-control"] == "no-store"
        for line in response.iter_lines():
            if line.startswith("event:"):
                arrivals.append(time.monotonic() - started)
    assert len(arrivals) == 5
    assert arrivals[0] >= 0.15  # también antes del primero: así se ve «Preparando…»
    assert arrivals[-1] - arrivals[0] >= 0.5  # y entre unos y otros: el primero llega mucho antes que el último
    assert all(later - earlier >= 0.1 for earlier, later in zip(arrivals, arrivals[1:], strict=False))


def test_a_client_that_leaves_stops_the_answer(double: AgentsServer) -> None:
    total = len(chat_reply("answer_length") or [])
    body = say("[fixture:answer_length][pace=200]").model_dump_json()
    with httpx.stream("POST", f"{double.url}/v1/chat", content=body, headers=CHAT_HEADERS, timeout=10) as response:
        next(response.iter_lines())  # el primer evento y se va
    time.sleep(total * 0.2 + 0.6)  # lo que habría tardado en terminar
    assert 1 <= double.chat_events_sent < total


def test_no_marker_or_an_unknown_example_is_a_client_error(double: AgentsServer) -> None:
    assert post_chat(double, say("sin marcador").model_dump_json().encode()).status_code == 400
    assert post_chat(double, say("[fixture:no_existe]").model_dump_json().encode()).status_code == 400
    assert post_chat(double, say("[fixture:answer_with_citation]").model_dump_json().encode()).status_code == 200


def test_the_chat_needs_the_key_the_contract_version_and_the_request_id(double: AgentsServer) -> None:
    assert post_chat(double).status_code == 200
    assert post_chat(double, Authorization="Bearer otra-clave").status_code == 401
    assert post_chat(double, Authorization="").status_code == 401
    assert post_chat(double, **{"X-Cuadre-Contract-Version": "2"}).status_code == 400
    assert post_chat(double, **{"X-Request-Id": ""}).status_code == 400
    _, error = drain_frames(HttpAgentsClient(double.url, "otra-clave").stream_chat(say("x"), request_id="r"))
    assert isinstance(error, AgentsError) and error.http_status == 401


def test_a_chat_body_that_breaks_the_contract_is_rejected(double: AgentsServer) -> None:
    valid = json.loads(say("[fixture:answer_with_citation]").model_dump_json())
    bodies = [
        b"",
        b"no es json",
        b'{"conversation_id": "no-uuid"}',
        json.dumps({**valid, "messages": []}).encode(),
        json.dumps(
            {**valid, "messages": [{"role": "assistant", "content": "[fixture:answer_with_citation]"}]}
        ).encode(),
    ]
    for body in bodies:
        assert post_chat(double, body).status_code == 400


def test_the_chat_agent_takes_no_tools_yet(double: AgentsServer) -> None:
    with_tools = say("[fixture:answer_with_citation]", tools=True).model_dump_json().encode()
    assert post_chat(double, with_tools, **{"X-User-Token": "token-mcp-sintetico"}).status_code == 400
    assert post_chat(double, with_tools).status_code == 400  # `mcp_url` sin herramientas que lo atiendan
    assert post_chat(double, **{"X-User-Token": "token-mcp-sintetico"}).status_code == 400  # token sin `mcp_url`


def test_the_chat_writes_nothing_about_the_message(double: AgentsServer, capfd: pytest.CaptureFixture[str]) -> None:
    ask(double, "MENSAJE-SECRETO-DE-PRUEBA [fixture:answer_with_citation]")
    out, err = capfd.readouterr()
    assert "MENSAJE-SECRETO-DE-PRUEBA" not in out + err and "fixture:" not in out + err


def test_a_history_bigger_than_an_extract_request_is_accepted(double: AgentsServer) -> None:
    data = json.loads(say("x").model_dump_json())
    data["messages"] = [{"role": "user" if i % 2 == 0 else "assistant", "content": "a" * 8000} for i in range(9)]
    data["messages"].append({"role": "user", "content": "[fixture:answer_with_citation]"})
    body = json.dumps(data).encode()
    assert 65_536 < len(body) < 262_144  # más que el tope de una lectura de factura, menos que el de un chat
    assert post_chat(double, body).status_code == 200
