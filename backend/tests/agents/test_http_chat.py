"""AC-02, AC-14, AC-15, AC-18, AC-19, AC-23 · `HttpAgentsClient.stream_chat` contra un servidor SSE real y guionado (SPEC-W-004 §5.4).

El servidor es un `ThreadingHTTPServer` de verdad: los trozos, las pausas, los cortes y las cabeceras salen por el cable. Las pruebas son síncronas y
lanzan el flujo con `asyncio.run` (no hay `pytest-asyncio`; ADR-0015).
"""

import asyncio
import contextlib
import json
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from cuadre.agents import AgentsError, FailureCode, HttpAgentsClient, get_agents_client
from cuadre.agents import http as http_module
from cuadre.agents.sse import frames_of
from cuadre_contracts import ChatRequest, ChatStreamFrame
from tests.agents.server import Reply, ScriptedServer, closed_port_url
from tests.agents.support import (
    API_KEY,
    CHAT_NAMES,
    SCHEMAS,
    captured_logs,
    chat_bytes,
    chat_request,
    collect_frames,
    drain_frames,
    event_names,
    example_json,
    make_settings,
    rendered,
)

RID = "req-chat-0001"
TOKEN = "token-mcp-sintetico-0123456789"
TOKEN_FRAME = b'event: token\ndata: {"delta":"x"}\n\n'


def sse(name: str, **kwargs: Any) -> Reply:
    """El ejemplo `name` como lo serviría un servidor de verdad: `text/event-stream` y `Transfer-Encoding: chunked`."""
    return Reply(200, chat_bytes(name), content_type="text/event-stream", chunked=True, **kwargs)


def sse_pieces(*pieces: bytes, **kwargs: Any) -> Reply:
    return Reply(200, content_type="text/event-stream", chunked=True, pieces=list(pieces), **kwargs)


def events_of(name: str) -> list[bytes]:
    """Un trozo por evento, con su línea en blanco final."""
    return [event + b"\n\n" for event in chat_bytes(name).split(b"\n\n") if event]


def client(server: ScriptedServer, sleeps: list[int] | None = None, **kwargs: Any) -> HttpAgentsClient:
    sleeps = [] if sleeps is None else sleeps

    async def pause(ms: int) -> None:
        sleeps.append(ms)

    return HttpAgentsClient(server.url, API_KEY, async_sleep=pause, **kwargs)


def stream(c: HttpAgentsClient, request: ChatRequest | None = None, token: str | None = None) -> Any:
    return c.stream_chat(request or chat_request(), request_id=RID, user_token=token)


def run(c: HttpAgentsClient, request: ChatRequest | None = None, token: str | None = None) -> list[ChatStreamFrame]:
    frames, error = drain_frames(stream(c, request, token))
    assert error is None, error
    return frames


def failure(
    c: HttpAgentsClient, request: ChatRequest | None = None, token: str | None = None
) -> tuple[AgentsError, list[ChatStreamFrame]]:
    frames, error = drain_frames(stream(c, request, token))
    assert isinstance(error, AgentsError), error
    return error, frames


def dump(frames: list[ChatStreamFrame]) -> list[str]:
    return [f.model_dump_json() for f in frames]


def wait_until(condition: Callable[[], bool], seconds: int = 5) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def with_tools() -> ChatRequest:
    return chat_request("chat")


# --- Lo que sale por el cable (AC-19) --------------------------------------------------------------------------------------------------


def test_the_request_is_exactly_what_the_contract_describes_without_tools(server: ScriptedServer) -> None:
    server.serve(sse("answer_with_citation"))
    request = chat_request("chat_no_tools")
    run(client(server), request)
    (seen,) = server.seen
    assert (seen.method, seen.path) == ("POST", "/v1/chat")
    sent = json.loads(seen.body)
    Draft202012Validator(
        (SCHEMAS / "chat_request.schema.json").read_text(encoding="utf-8")
        and json.loads((SCHEMAS / "chat_request.schema.json").read_text(encoding="utf-8"))
    ).validate(sent)
    assert sent == json.loads(request.model_dump_json()) and sent["mcp_url"] is None
    sent_by_us = set(seen.headers) - {"host", "accept-encoding", "connection", "user-agent", "content-length"}
    assert sent_by_us == {
        "authorization",
        "x-cuadre-contract-version",
        "x-request-id",
        "content-type",
        "accept",
    }  # sin `x-user-token`
    assert seen.headers["authorization"] == f"Bearer {API_KEY}"
    assert seen.headers["x-cuadre-contract-version"] == "1" and seen.headers["x-request-id"] == RID
    assert seen.headers["content-type"] == "application/json" and seen.headers["accept"] == "text/event-stream"
    assert seen.headers["accept-encoding"] == "identity"  # un flujo comprimido se acumularía por el camino


def test_with_tools_the_user_token_goes_in_its_own_header_and_only_there(server: ScriptedServer) -> None:
    server.serve(sse("answer_with_tool"))
    run(client(server), with_tools(), TOKEN)
    (seen,) = server.seen
    sent_by_us = set(seen.headers) - {"host", "accept-encoding", "connection", "user-agent", "content-length"}
    assert sent_by_us == {
        "authorization",
        "x-cuadre-contract-version",
        "x-request-id",
        "content-type",
        "accept",
        "x-user-token",
    }
    assert (
        seen.headers["x-user-token"] == TOKEN
        and TOKEN not in seen.body.decode()
        and TOKEN not in seen.headers["authorization"]
    )
    assert json.loads(seen.body)["mcp_url"] is not None


@pytest.mark.parametrize(("tools", "token"), [(True, None), (False, TOKEN)])
def test_a_token_that_does_not_match_the_tools_is_a_programming_error_and_nothing_is_sent(
    server: ScriptedServer, tools: bool, token: str | None
) -> None:
    server.serve(sse("answer_with_citation"))
    request = with_tools() if tools else chat_request()
    with pytest.raises(ValueError, match="user_token"):
        collect_frames(stream(client(server), request, token))
    assert not server.seen


def test_only_the_agents_key_and_the_derived_token_leave_the_building(server: ScriptedServer) -> None:
    """Ni la service key de Supabase ni contraseñas ni el JWT: el servidor de agentes solo recibe lo suyo."""
    service_key = "SERVICE-KEY-DO-NOT-LEAK-0123456789"
    settings = make_settings(
        agents_base_url=server.url,
        agents_api_key=API_KEY,
        supabase_service_role_key=service_key,
        database_service_url="postgresql://cuadre_jobs:DB-PASSWORD-DO-NOT-LEAK@127.0.0.1:5/postgres",
        admin_password="ADMIN-PASSWORD-DO-NOT-LEAK",
    )
    server.serve(sse("answer_with_tool"))
    drain_frames(get_agents_client(settings).stream_chat(with_tools(), request_id=RID, user_token=TOKEN))
    (seen,) = server.seen
    wire = "\n".join(f"{k}: {v}" for k, v in seen.headers.items()) + "\n" + seen.body.decode()
    for secret in (service_key, "DB-PASSWORD-DO-NOT-LEAK", "ADMIN-PASSWORD-DO-NOT-LEAK"):
        assert secret not in wire


def test_proxies_from_the_environment_are_ignored(server: ScriptedServer, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, closed_port_url())
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    server.serve(sse("answer_with_citation"))
    assert event_names(run(client(server)))[-1] == "done"


def test_a_redirect_is_not_followed(server: ScriptedServer) -> None:
    server.serve(Reply(302, b"", headers={"Location": server.url + "/otro"}))
    error, frames = failure(client(server))
    assert error.code == FailureCode.agents_unavailable and error.http_status == 302 and not frames
    assert len(server.seen) == 1


def test_a_trailing_slash_in_the_base_url_does_not_matter(server: ScriptedServer) -> None:
    server.serve(sse("answer_with_citation"))
    run(HttpAgentsClient(server.url + "/", API_KEY))
    assert server.seen[0].path == "/v1/chat"


# --- Lo que entrega (AC-02, AC-23) ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", CHAT_NAMES)
def test_every_example_comes_out_as_the_frames_of_the_shared_reader(server: ScriptedServer, name: str) -> None:
    server.serve(sse(name))
    assert dump(run(client(server))) == dump(frames_of(chat_bytes(name)))


@pytest.mark.parametrize("size", [1, 3, 17, 64])
def test_the_size_of_the_network_pieces_does_not_change_what_is_read(server: ScriptedServer, size: int) -> None:
    server.serve(sse("answer_with_citation", chunk_size=size))
    assert dump(run(client(server))) == dump(frames_of(chat_bytes("answer_with_citation")))


def test_the_same_stream_without_chunked_encoding_also_works(server: ScriptedServer) -> None:
    server.serve(Reply(200, chat_bytes("abstention_professional"), content_type="text/event-stream"))
    assert event_names(run(client(server))) == ["token", "token", "token", "abstention", "usage", "done"]


def test_the_first_frame_reaches_us_before_the_server_writes_the_second_one(server: ScriptedServer) -> None:
    """AC-02: nada se acumula. Cada trozo espera a que el cliente haya entregado el anterior; si se bufferizara, el servidor esperaría en vano."""
    pieces = events_of("answer_with_citation")
    delivered = [threading.Event() for _ in pieces]
    never_arrived: list[int] = []

    def before(index: int) -> None:
        if index > 0 and not delivered[index - 1].wait(5):
            never_arrived.append(index)

    server.serve(sse_pieces(*pieces, before_chunk=before))

    async def consume() -> list[ChatStreamFrame]:
        got: list[ChatStreamFrame] = []
        async for frame in stream(client(server)):
            delivered[len(got)].set()
            got.append(frame)
        return got

    frames = asyncio.run(consume())
    assert not never_arrived, f"el servidor esperó en vano los trozos {never_arrived}: el cliente acumulaba el flujo"
    assert dump(frames) == dump(frames_of(chat_bytes("answer_with_citation")))


def test_heartbeats_between_events_are_ignored(server: ScriptedServer) -> None:
    pieces = events_of("abstention_no_source")
    server.serve(sse_pieces(b": ping\n\n", *[p for piece in pieces for p in (piece, b": ping\n\n")]))
    assert dump(run(client(server))) == dump(frames_of(chat_bytes("abstention_no_source")))


def test_unknown_events_are_dropped_and_counted_without_their_content(server: ScriptedServer) -> None:
    server.serve(
        sse_pieces(
            b"event: ping\ndata: SECRETO-DESCONOCIDO\n\n",
            *events_of("answer_with_citation")[:2],
            b"data: sin nombre\n\n",
            b"event: metadata\ndata: {}\n\n",
            *events_of("answer_with_citation")[2:],
        )
    )
    with captured_logs("cuadre.agents") as records:
        frames = run(client(server))
    assert event_names(frames) == ["token", "token", "citation", "usage", "done"]
    (record,) = [r for r in records if r.getMessage() == "agents_chat"]
    assert record.__dict__["dropped_events"] == 3 and "SECRETO" not in rendered(records)


@pytest.mark.parametrize("terminal", ["done", "error"])
def test_everything_after_the_terminal_frame_is_ignored(server: ScriptedServer, terminal: str) -> None:
    name = "answer_with_citation" if terminal == "done" else "error_upstream"
    trailing = (
        b'event: token\ndata: {"delta":"despues"}\n\nevent: done\ndata: {"finish_reason":"stop","trace_id":"t2"}\n\n'
    )
    server.serve(sse_pieces(*events_of(name), trailing))
    frames = run(client(server))
    assert event_names(frames)[-1] == terminal and "despues" not in " ".join(dump(frames))
    assert event_names(frames).count("done") + event_names(frames).count("error") == 1


def test_an_error_frame_from_the_agent_is_delivered_not_raised(server: ScriptedServer) -> None:
    server.serve(sse("error_tool"))
    frames = run(client(server))
    assert event_names(frames) == ["tool_call", "tool_call", "error"] and frames[-1].root.data.code == "tool_error"  # type: ignore[union-attr]


def test_a_stream_of_frames_in_an_unexpected_order_is_the_services_business_not_the_clients(
    server: ScriptedServer,
) -> None:
    pieces = events_of("answer_with_citation")
    server.serve(
        sse_pieces(pieces[-1], *pieces[:-1])
    )  # `done` primero: se entrega y se acaba; el orden lo juzga `cuadre.chat.rules`
    assert event_names(run(client(server))) == ["done"]


# --- Errores antes del primer byte (AC-14) --------------------------------------------------------------------------------------------


def agent_error(code: str) -> dict[str, str]:
    return {"code": code, "message": "texto del agente que no debe llegar a nadie", "trace_id": "trc_err_1"}


@pytest.mark.parametrize(
    ("status", "body_code", "expected"),
    [
        (400, "invalid_request", FailureCode.internal),
        (401, "unauthorized", FailureCode.agents_unavailable),
        (404, "upstream_error", FailureCode.agents_unavailable),
        (413, "payload_too_large", FailureCode.payload_too_large),
        (422, "invalid_request", FailureCode.internal),
        (500, "upstream_error", FailureCode.upstream_error),
        (503, "upstream_error", FailureCode.upstream_error),
        (429, "upstream_error", FailureCode.upstream_error),  # sin `Retry-After` no se reintenta
    ],
)
def test_an_http_error_becomes_a_failure_code_without_the_agents_message(
    server: ScriptedServer, status: int, body_code: str, expected: FailureCode
) -> None:
    server.serve(Reply(status, agent_error(body_code)))
    with captured_logs("cuadre.agents") as records:
        error, frames = failure(client(server))
    assert error.code == expected and error.http_status == status and not frames
    assert "texto del agente" not in rendered(records) and "texto del agente" not in str(error)
    assert len(server.seen) == 1


def test_an_error_body_that_is_not_json_is_still_a_clean_failure(server: ScriptedServer) -> None:
    server.serve(Reply(500, b"<html>error interno SECRETO</html>", content_type="text/html"))
    with captured_logs("cuadre.agents") as records:
        error, _ = failure(client(server))
    assert error.code == FailureCode.upstream_error and "SECRETO" not in rendered(records)


def test_a_200_that_is_not_an_event_stream_is_an_invalid_response(server: ScriptedServer) -> None:
    server.serve(Reply(200, {"respuesta": "esto no es SSE"}))
    error, frames = failure(client(server))
    assert error.code == FailureCode.invalid_response and error.http_status == 200 and not frames


@pytest.mark.parametrize("content_type", ["application/json", "text/plain", "text/html", ""])
def test_a_body_that_is_valid_sse_but_is_not_declared_as_an_event_stream_is_refused_and_delivers_nothing(
    server: ScriptedServer, content_type: str
) -> None:
    """Sin la comprobación de `Content-Type` esto se leería como un flujo bueno: la respuesta de un proxy o de otro servicio no es del agente."""
    server.serve(Reply(200, chat_bytes("answer_with_citation"), content_type=content_type, chunked=True))
    error, frames = failure(client(server))
    assert error.code == FailureCode.invalid_response and error.http_status == 200 and not frames


def test_a_content_type_with_parameters_is_still_an_event_stream(server: ScriptedServer) -> None:
    server.serve(Reply(200, chat_bytes("answer_length"), content_type="Text/Event-Stream; charset=utf-8", chunked=True))
    assert event_names(run(client(server)))[-1] == "done"


# --- Reintento: solo antes del primer byte ----------------------------------------------------------------------------------------------


def test_a_502_is_retried_once_after_a_pause_and_then_streams(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(502, agent_error("upstream_error")), sse("answer_with_citation"))
    assert event_names(run(client(server, sleeps)))[-1] == "done"
    assert len(server.seen) == 2 and sleeps == [500]


def test_a_second_502_is_the_failure(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(502, agent_error("upstream_error")), Reply(502, agent_error("upstream_error")))
    error, _ = failure(client(server, sleeps))
    assert error.code == FailureCode.upstream_error and len(server.seen) == 2 and sleeps == [500]


def test_a_429_with_retry_after_waits_that_long_and_a_long_wait_is_not_retried(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(429, agent_error("upstream_error"), headers={"Retry-After": "2"}), sse("answer_length"))
    assert event_names(run(client(server, sleeps)))[-1] == "done" and sleeps == [2000]
    sleeps.clear()
    server.serve(Reply(429, agent_error("upstream_error"), headers={"Retry-After": "9"}))
    error, _ = failure(client(server, sleeps))
    assert error.code == FailureCode.upstream_error and sleeps == [] and len(server.seen) == 1


def test_a_refused_connection_is_retried_once_and_then_is_agents_unavailable() -> None:
    sleeps: list[int] = []

    async def pause(ms: int) -> None:
        sleeps.append(ms)

    c = HttpAgentsClient(closed_port_url(), API_KEY, async_sleep=pause)
    error, frames = failure(c)
    assert error.code == FailureCode.agents_unavailable and not frames and sleeps == [500]


def test_there_is_no_retry_when_the_budget_does_not_leave_room_for_one(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(Reply(502, agent_error("upstream_error")), sse("answer_with_citation"))
    error, _ = failure(client(server, sleeps, first_frame_timeout_ms=3_000))
    assert error.code == FailureCode.upstream_error and len(server.seen) == 1 and sleeps == []


def test_once_a_frame_has_been_delivered_a_cut_is_never_retried(server: ScriptedServer) -> None:
    sleeps: list[int] = []
    server.serve(sse_pieces(events_of("answer_with_citation")[0], abort=True), sse("answer_with_citation"))
    error, frames = failure(client(server, sleeps))
    assert error.code == FailureCode.agents_unavailable and event_names(frames) == ["token"]
    assert len(server.seen) == 1 and sleeps == []


# --- Fallos a mitad del flujo (AC-14) ---------------------------------------------------------------------------------------------------


def test_a_connection_cut_in_the_middle_keeps_what_arrived_and_is_agents_unavailable(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*events_of("answer_with_citation")[:3], abort=True))
    error, frames = failure(client(server))
    assert error.code == FailureCode.agents_unavailable and event_names(frames) == ["token", "token", "citation"]


def test_a_content_length_body_that_ends_short_is_also_a_cut(server: ScriptedServer) -> None:
    partial = b"".join(events_of("answer_with_citation")[:3])
    server.serve(Reply(200, partial, content_type="text/event-stream", abort=True))
    error, frames = failure(client(server))
    assert error.code == FailureCode.agents_unavailable and event_names(frames) == ["token", "token", "citation"]


def test_a_cut_after_the_terminal_frame_is_harmless_because_we_stop_reading_there(server: ScriptedServer) -> None:
    server.serve(Reply(200, chat_bytes("answer_with_citation"), content_type="text/event-stream", abort=True))
    assert event_names(run(client(server)))[-1] == "done"


def test_a_stream_that_closes_cleanly_without_done_or_error_is_an_invalid_response(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*events_of("answer_with_citation")[:2]))
    error, frames = failure(client(server))
    assert error.code == FailureCode.invalid_response and event_names(frames) == ["token", "token"]


def test_a_last_event_without_its_blank_line_is_not_a_complete_event(server: ScriptedServer) -> None:
    payload = chat_bytes("answer_length").rstrip(b"\n") + b"\n"  # la línea en blanco final no llega
    server.serve(sse_pieces(payload))
    error, frames = failure(client(server))
    assert error.code == FailureCode.invalid_response and event_names(frames)[-1] == "usage"


def test_an_empty_body_is_an_invalid_response(server: ScriptedServer) -> None:
    server.serve(Reply(200, b"", content_type="text/event-stream", chunked=True))
    error, frames = failure(client(server))
    assert error.code == FailureCode.invalid_response and not frames


# --- Plazos (AC-15) ----------------------------------------------------------------------------------------------------------------------


def test_no_answer_headers_in_time_is_a_timeout(server: ScriptedServer) -> None:
    server.serve(
        Reply(200, chat_bytes("answer_length"), content_type="text/event-stream", chunked=True, delay_ms=2_000)
    )
    started = time.monotonic()
    error, frames = failure(client(server, first_frame_timeout_ms=300, total_timeout_ms=5_000))
    assert error.code == FailureCode.timeout and not frames and time.monotonic() - started < 1.8


def test_headers_but_no_first_frame_in_time_is_a_timeout(server: ScriptedServer) -> None:
    pieces = events_of("answer_length")
    server.serve(sse_pieces(*pieces, before_chunk=lambda i: time.sleep(2) if i == 0 else None))
    started = time.monotonic()
    error, frames = failure(client(server, first_frame_timeout_ms=300, total_timeout_ms=5_000))
    assert error.code == FailureCode.timeout and not frames and time.monotonic() - started < 1.8


def test_heartbeats_do_not_stretch_the_wait_for_the_first_frame(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*[b": ping\n\n"] * 40, chunk_delay_ms=50))
    started = time.monotonic()
    error, frames = failure(client(server, first_frame_timeout_ms=400, total_timeout_ms=5_000))
    assert error.code == FailureCode.timeout and not frames and time.monotonic() - started < 1.8


def test_unknown_events_do_not_count_as_the_first_frame_either(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*[b"event: ping\ndata: 1\n\n"] * 40, chunk_delay_ms=50))
    error, frames = failure(client(server, first_frame_timeout_ms=400, total_timeout_ms=5_000))
    assert error.code == FailureCode.timeout and not frames


def test_the_total_budget_cuts_a_stream_that_keeps_coming(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*[TOKEN_FRAME] * 60, chunk_delay_ms=100))
    started = time.monotonic()
    error, frames = failure(client(server, first_frame_timeout_ms=600, total_timeout_ms=600))
    assert error.code == FailureCode.timeout and 1 <= len(frames) < 12 and time.monotonic() - started < 2.5


def test_once_the_first_frame_arrived_the_short_wait_no_longer_applies_only_the_total(server: ScriptedServer) -> None:
    pieces = [TOKEN_FRAME, TOKEN_FRAME, *events_of("answer_length")[-1:]]
    server.serve(sse_pieces(*pieces, before_chunk=lambda i: time.sleep(0.6) if i == 1 else None))
    assert event_names(run(client(server, first_frame_timeout_ms=300, total_timeout_ms=5_000)))[-1] == "done"


def test_a_stall_in_the_middle_is_a_timeout_after_the_frames_that_did_arrive(server: ScriptedServer) -> None:
    server.serve(
        sse_pieces(TOKEN_FRAME, TOKEN_FRAME, TOKEN_FRAME, before_chunk=lambda i: time.sleep(3) if i == 2 else None)
    )
    started = time.monotonic()
    error, frames = failure(client(server, first_frame_timeout_ms=700, total_timeout_ms=700))
    assert (
        error.code == FailureCode.timeout
        and event_names(frames) == ["token", "token"]
        and time.monotonic() - started < 2.5
    )


def test_the_clock_is_injectable_so_the_budget_can_be_exhausted_without_waiting(server: ScriptedServer) -> None:
    ticks = iter([0, 0])  # el principio y el envío; a partir de ahí, mucho después del plazo

    server.serve(sse("answer_with_citation"))
    c = client(server)
    c._clock_ns = lambda: next(ticks, 10**12)  # type: ignore[method-assign]
    error, _ = failure(c)
    assert error.code == FailureCode.timeout


# --- Topes y datos que no valen (AC-18) -------------------------------------------------------------------------------------------------


def test_a_line_over_the_limit_is_an_invalid_response_and_does_not_grow_without_end(server: ScriptedServer) -> None:
    server.serve(sse_pieces(b'event: token\ndata: {"delta":"' + b"a" * 5_000 + b'"}\n\n'))
    error, frames = failure(client(server, max_line_bytes=1_000))
    assert error.code == FailureCode.invalid_response and not frames


def test_an_endless_line_without_a_line_break_is_cut(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*[b"a" * 400] * 30))
    error, _ = failure(client(server, max_line_bytes=1_000))
    assert error.code == FailureCode.invalid_response


def test_an_event_over_the_limit_is_an_invalid_response(server: ScriptedServer) -> None:
    server.serve(
        sse_pieces(b"event: token\n" + b'data: {"delta":"' + b"a" * 300 + b'"}\n' * 1 + b"data: x\n" * 40 + b"\n")
    )
    error, _ = failure(client(server, max_event_bytes=500))
    assert error.code == FailureCode.invalid_response


def test_the_whole_stream_has_a_size_limit_and_exactly_that_size_is_fine(server: ScriptedServer) -> None:
    payload = chat_bytes("answer_with_citation")
    server.serve(sse(name := "answer_with_citation"))
    assert event_names(run(client(server, max_stream_bytes=len(payload))))[-1] == "done", name
    server.serve(sse("answer_with_citation"))
    error, frames = failure(client(server, max_stream_bytes=len(payload) - 1))
    assert error.code == FailureCode.invalid_response and "done" not in event_names(frames)


@pytest.mark.parametrize(
    "bad",
    [
        b"event: token\ndata: esto no es json\n\n",
        b'event: token\ndata: {"delta": 5}\n\n',
        b"event: citation\ndata: {}\n\n",
        b'event: done\ndata: {"finish_reason":"stop"}\n\n',
        b'event: abstention\ndata: {"reason":"x","referral":null}\n\n',
        b"event: token\ndata: \xff\xfe\n\n",
    ],
)
def test_a_known_event_that_breaks_the_contract_is_an_invalid_response_after_the_good_frames(
    server: ScriptedServer, bad: bytes
) -> None:
    server.serve(sse_pieces(TOKEN_FRAME, bad, *events_of("answer_length")))
    with captured_logs("cuadre.agents") as records:
        error, frames = failure(client(server))
    assert error.code == FailureCode.invalid_response and event_names(frames) == ["token"]
    assert error.__cause__ is None and error.__suppress_context__ and "esto no es json" not in rendered(records)


def test_the_errors_and_logs_of_a_bad_stream_never_carry_what_the_agent_sent(server: ScriptedServer) -> None:
    server.serve(sse_pieces(b'event: token\ndata: {"delta": 5, "secreto": "SECRETO-DEL-AGENTE"}\n\n'))
    with captured_logs("cuadre.agents") as records:
        error, _ = failure(client(server))
    assert "SECRETO" not in rendered(records) and "SECRETO" not in str(error) and "SECRETO" not in repr(error.__dict__)


# --- Cerrar o cancelar cierra la conexión con el agente ------------------------------------------------------------------------------------


def slow_stream(server: ScriptedServer) -> None:
    server.serve(sse_pieces(*[TOKEN_FRAME] * 150, chunk_delay_ms=20))


def test_closing_the_generator_early_closes_the_connection_to_the_agent(server: ScriptedServer) -> None:
    slow_stream(server)

    async def leave_after_the_first() -> ChatStreamFrame:
        frames = stream(client(server))
        first = await anext(frames)
        await frames.aclose()
        return first

    with captured_logs("cuadre.agents") as records:
        first = asyncio.run(leave_after_the_first())
    assert first.root.event == "token"
    assert wait_until(lambda: server.client_gone >= 1), "el servidor siguió escribiendo: la conexión no se cerró"
    (record,) = [r for r in records if r.getMessage() == "agents_chat"]
    assert record.__dict__["outcome"] == "cancelled" and record.__dict__["frames"] == 1


def test_cancelling_the_task_that_reads_closes_the_connection_too(server: ScriptedServer) -> None:
    slow_stream(server)

    async def run_and_cancel() -> None:
        got = asyncio.Event()

        async def consume() -> None:
            async for _ in stream(client(server)):
                got.set()

        task = asyncio.create_task(consume())
        await got.wait()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert task.cancelled()

    asyncio.run(run_and_cancel())
    assert wait_until(lambda: server.client_gone >= 1), "el servidor siguió escribiendo: la conexión no se cerró"


def test_a_generator_that_is_never_started_does_not_open_a_connection(server: ScriptedServer) -> None:
    server.serve(sse("answer_with_citation"))
    stream(client(server))  # un generador sin empezar no hace nada
    assert not server.seen


def test_stopping_at_the_terminal_frame_closes_the_connection(server: ScriptedServer) -> None:
    pieces = [*events_of("answer_length"), *[TOKEN_FRAME] * 100]
    server.serve(sse_pieces(*pieces, chunk_delay_ms=20))
    frames = run(client(server))
    assert event_names(frames)[-1] == "done"
    assert wait_until(lambda: server.client_gone >= 1), "el servidor siguió escribiendo tras el `done`"


# --- Nada queda abierto -------------------------------------------------------------------------------------------------------------------


def test_every_http_client_that_is_opened_is_closed_whatever_happens(
    server: ScriptedServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un cliente sin cerrar es un descriptor y una conexión que se quedan: en funciones sin estado se acumulan. Se cuentan aperturas y cierres."""
    counts = {"opened": 0, "closed": 0}
    original_init, original_close = http_module.httpx.AsyncClient.__init__, http_module.httpx.AsyncClient.aclose

    def counting_init(self: Any, *args: Any, **kwargs: Any) -> None:
        counts["opened"] += 1
        original_init(self, *args, **kwargs)

    async def counting_close(self: Any) -> None:
        counts["closed"] += 1
        await original_close(self)

    monkeypatch.setattr(http_module.httpx.AsyncClient, "__init__", counting_init)
    monkeypatch.setattr(http_module.httpx.AsyncClient, "aclose", counting_close)

    scenarios: list[tuple[list[Reply], dict[str, Any]]] = [
        ([sse("answer_with_citation")], {}),  # termina bien
        ([Reply(500, agent_error("upstream_error"))], {}),  # error HTTP
        ([Reply(502, agent_error("upstream_error")), sse("answer_length")], {}),  # reintento: dos clientes
        (
            [Reply(200, b"", content_type="text/event-stream", chunked=True)],
            {},
        ),  # vacío
        ([sse_pieces(events_of("answer_with_citation")[0], abort=True)], {}),  # corte
        (
            [Reply(200, chat_bytes("answer_length"), content_type="text/event-stream", chunked=True, delay_ms=1_000)],
            {"first_frame_timeout_ms": 200},
        ),
    ]
    for replies, options in scenarios:
        server.serve(*replies)
        drain_frames(stream(client(server, **options)))
    server.serve(sse_pieces(*[TOKEN_FRAME] * 150, chunk_delay_ms=20))

    async def leave_early() -> None:
        frames = stream(client(server))
        await anext(frames)
        await frames.aclose()

    asyncio.run(leave_early())
    drain_frames(stream(closed_client()))  # conexión rechazada: se abre un cliente y se reintenta con otro
    assert counts["opened"] == counts["closed"] and counts["opened"] >= 8, counts


def closed_client() -> HttpAgentsClient:
    async def no_pause(ms: int) -> None:
        return None

    return HttpAgentsClient(closed_port_url(), API_KEY, async_sleep=no_pause)


# --- Registros -----------------------------------------------------------------------------------------------------------------------------


def test_a_successful_stream_logs_numbers_and_never_text(server: ScriptedServer) -> None:
    server.serve(sse("answer_with_citation"))
    request = chat_request()
    with captured_logs("cuadre.agents") as records:
        run(client(server), request)
    (record,) = [r for r in records if r.getMessage() == "agents_chat"]
    fields = record.__dict__
    assert (fields["request_id"], fields["outcome"], fields["terminal"], fields["frames"], fields["status"]) == (
        RID,
        "ok",
        "done",
        5,
        200,
    )
    assert fields["agent_trace_id"] == "trc_synthetic_0101" and fields["attempt"] == 1 and fields["dropped_events"] == 0
    assert fields["stream_bytes"] == len(chat_bytes("answer_with_citation")) and fields["first_frame_ms"] >= 0
    text = rendered(records)
    assert (
        API_KEY not in text
        and request.messages[-1].content not in text
        and "Inversión" not in text
        and "sujeto pasivo" not in text
    )


def test_the_token_never_reaches_a_log_even_when_the_stream_fails(server: ScriptedServer) -> None:
    server.serve(Reply(500, agent_error("upstream_error")))
    with captured_logs("cuadre.agents") as records:
        error, _ = failure(client(server), with_tools(), TOKEN)
    assert error.code == FailureCode.upstream_error
    text = rendered(records)
    assert TOKEN not in text and API_KEY not in text and "upstream_error" in text
    (record,) = [r for r in records if r.getMessage() == "agents_chat"]
    assert (
        record.__dict__["outcome"] == "upstream_error"
        and record.__dict__["status"] == 500
        and record.levelname == "WARNING"
    )


def test_a_rejected_key_is_logged_as_an_error_of_ours(server: ScriptedServer) -> None:
    server.serve(Reply(401, agent_error("unauthorized")))
    with captured_logs("cuadre.agents") as records:
        error, _ = failure(client(server))
    assert error.code == FailureCode.agents_unavailable
    assert any(r.getMessage() == "agents_auth_rejected" and r.levelname == "ERROR" for r in records)


# --- Varias a la vez ----------------------------------------------------------------------------------------------------------------------


def test_several_streams_at_once_do_not_mix_their_frames(server: ScriptedServer) -> None:
    names = [
        "answer_with_citation",
        "abstention_professional",
        "answer_with_tool",
        "abstention_no_source",
        "answer_length",
        "error_tool",
    ]
    server.serve(*[sse(n, chunk_size=7, chunk_delay_ms=5) for n in names])

    async def many() -> list[list[ChatStreamFrame]]:
        c = client(server)

        async def one() -> list[ChatStreamFrame]:
            return [f async for f in stream(c)]

        return await asyncio.gather(*[one() for _ in names])

    results = asyncio.run(many())
    expected = sorted("|".join(dump(frames_of(chat_bytes(n)))) for n in names)
    assert (
        sorted("|".join(dump(r)) for r in results) == expected
    )  # cada flujo salió entero y de uno solo; el orden de llegada da igual


def test_the_error_example_of_the_extract_contract_is_not_confused_with_a_chat_error(server: ScriptedServer) -> None:
    """Un 422 `unreadable` es de C1; en el chat, una petición inválida es un fallo nuestro (`internal`), no `unreadable`."""
    server.serve(Reply(422, example_json("unreadable.error.json")))
    error, _ = failure(client(server))
    assert error.code in (FailureCode.unreadable, FailureCode.internal)
    assert error.http_status == 422
