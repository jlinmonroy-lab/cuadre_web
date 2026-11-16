"""AC-12, AC-14 a AC-18 · Lo que sale mal: roles, agente caído o lento, validación, tope por hora y contenido que no es de fiar (SPEC-W-004 §7)."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import PoolTimeout

from cuadre.agents import AgentsError, FailureCode, HttpAgentsClient
from cuadre.agents.sse import frames_of
from cuadre.chat import limits, rules
from cuadre.chat.service import ChatService
from tests.agents.server import Reply, ScriptedServer
from tests.agents.support import API_KEY, captured_logs, chat_bytes, rendered
from tests.chat.conftest import QUESTION, Api, conversation_count, stored
from tests.chat.fakes import BrokenAgent, EmptyAgent, frames

TEXT = "Respuesta de prueba"


def token_frames(*texts: str, done: str = '{"finish_reason":"stop","trace_id":"trc_t"}') -> list:  # type: ignore[type-arg]
    body = "".join(f'event: token\ndata: {{"delta":{json.dumps(t)}}}\n\n' for t in texts)
    return frames_of((body + f"event: done\ndata: {done}\n\n").encode())


def broken(*texts: str, error: BaseException | None = None) -> BrokenAgent:
    source = token_frames(*texts)[:-1]  # sin el `done`
    return BrokenAgent(source, error=error)


# --- AC-12 · Roles --------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_ac12_gestores_and_admins_cannot_use_the_chat_at_all(api: Api, who: str) -> None:
    api.script("answer_with_citation")
    person = api.cast[who]
    sent = api.send(person)
    assert sent.status == 403 and sent.problem is not None and sent.problem["code"] == "forbidden"
    assert api.request("GET", "/api/chat/conversations", person).status_code == 403
    assert api.request("GET", "/api/chat/conversations/00000000-0000-4000-8000-000000000001", person).status_code == 403
    assert (
        api.request("DELETE", "/api/chat/conversations/00000000-0000-4000-8000-000000000001", person).status_code == 403
    )
    assert api.rate(person, "00000000-0000-4000-8000-000000000001", "up").status_code == 403
    assert not api.agent.chat_calls


def test_ac12_a_suspended_account_and_a_request_without_a_session_are_refused(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("answer_with_citation")
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (api.cast.alicia.id,))
    sent = api.send(api.cast.alicia)
    assert sent.status == 403 and sent.problem is not None and sent.problem["code"] == "account_suspended"
    assert api.client.post("/api/chat", json={"conversation_id": None, "content": "hola"}).status_code == 401
    assert api.client.get("/api/chat/conversations").status_code == 401
    assert not api.agent.chat_calls


# --- AC-14 · El agente falla ----------------------------------------------------------------------------------------------------------


def test_ac14_an_agent_that_fails_before_the_first_frame_is_a_503_and_the_message_stays_saved(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script(AgentsError(FailureCode.upstream_error, http_status=502, trace_id="trc_secret"), "answer_with_citation")
    failed = api.send(api.cast.alicia)
    assert failed.status == 503 and failed.problem is not None
    assert failed.problem["code"] == "agent_unavailable" and failed.headers["retry-after"] == "5"
    assert failed.headers["content-type"].startswith("application/problem+json") and "trc_secret" not in failed.raw
    conversation = failed.problem["conversation_id"]
    rows = stored(admin, conversation)
    assert [(r["role"], r["content"]) for r in rows] == [("user", QUESTION)]  # el mensaje se guardó; no hay respuesta
    assert [c["id"] for c in api.conversations(api.cast.alicia)] == [conversation]

    retried = api.send(api.cast.alicia, QUESTION, conversation)  # «Reintentar»: la misma pregunta otra vez
    assert retried.terminal.name == "done"
    assert [r["role"] for r in stored(admin, conversation)] == ["user", "user", "assistant"]
    sent_to_agent = api.agent.chat_calls[-1].request.messages
    assert [m.role for m in sent_to_agent] == ["user"]  # la pregunta sin respuesta no se repite en el contexto


def test_ac14_an_agent_that_closes_without_a_single_frame_is_also_a_503(api: Api) -> None:
    api.use(EmptyAgent())
    sent = api.send(api.cast.alicia)
    assert sent.status == 503 and sent.problem is not None and sent.problem["code"] == "agent_unavailable"


def test_ac14_an_unexpected_failure_before_the_first_frame_is_a_500_without_details_and_the_agent_is_closed(
    api: Api,
) -> None:
    api.use(broken(error=RuntimeError("detalle interno SECRETO")))
    sent = api.send(api.cast.alicia)
    assert sent.status == 500 and "SECRETO" not in sent.raw


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AgentsError(FailureCode.agents_unavailable), "agent_unavailable"),
        (AgentsError(FailureCode.timeout), "timeout"),
        (AgentsError(FailureCode.upstream_error, http_status=500), "agent_error"),
        (AgentsError(FailureCode.invalid_response, http_status=200), "agent_error"),
        (RuntimeError("detalle interno SECRETO"), "agent_unavailable"),
    ],
)
def test_ac14_a_failure_in_the_middle_ends_the_stream_with_a_fixed_error_and_saves_what_arrived(
    api: Api, admin: Connection[DictRow], error: BaseException, code: str
) -> None:
    api.use(broken("Empiezo a respon", "der y", error=error))
    sent = api.send(api.cast.alicia)
    assert sent.status == 200 and sent.names == ["start", "token", "token", "error"]
    terminal = sent.terminal
    assert terminal.data == {"code": code, "message": rules.BROWSER_ERRORS[code], "message_id": str(sent.message_id)}
    assert "SECRETO" not in sent.raw
    _, assistant = stored(admin, sent.conversation_id)
    assert (assistant["status"], assistant["finish_reason"], assistant["content"], assistant["has_source"]) == (
        "error",
        "error",
        "Empiezo a responder y",
        None,
    )
    assert assistant["id"] == sent.message_id


def test_ac14_an_error_frame_from_the_agent_never_forwards_its_text(api: Api, admin: Connection[DictRow]) -> None:
    api.script("error_upstream")
    sent = api.send(api.cast.alicia)
    assert sent.names == ["start", "error"] and sent.terminal.data["code"] == "agent_error"
    assert "servicio de lenguaje" not in sent.raw
    assert stored(admin, sent.conversation_id)[1]["status"] == "error"


def test_ac14_a_done_that_says_error_and_a_stream_without_done_are_both_errors(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script(
        token_frames("a medias", done='{"finish_reason":"error","trace_id":"trc_e"}'),
        token_frames("sin final")[:-1],
    )
    first = api.send(api.cast.alicia)
    assert first.terminal.name == "error" and first.text == "a medias"
    second = api.send(api.cast.alicia)
    assert second.terminal.name == "error" and second.text == "sin final"
    assert [stored(admin, c.conversation_id)[1]["status"] for c in (first, second)] == ["error", "error"]


def test_ac14_if_the_answer_cannot_be_saved_the_stream_says_so_and_nothing_secret_is_logged(
    api: Api, monkeypatch: pytest.MonkeyPatch, admin: Connection[DictRow]
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise PoolTimeout("sin conexiones libres: datos SECRETOS")

    monkeypatch.setattr(ChatService, "_save", refuse)
    api.script("answer_with_citation")
    with captured_logs("cuadre") as records:
        sent = api.send(api.cast.alicia)
    assert sent.names[-1] == "error" and sent.terminal.data["code"] == "unavailable"
    assert sent.terminal.data["message"] == rules.BROWSER_ERRORS["unavailable"]
    assert [r["role"] for r in stored(admin, sent.conversation_id)] == [
        "user"
    ]  # la de la persona sí; la respuesta no pudo
    text = rendered(records)
    assert "chat_save_failed" in text and "SECRETOS" not in text and "PoolTimeout" in text


# --- AC-15 · Plazos (con el cliente HTTP real contra un servidor SSE lento) -------------------------------------------------------------


async def no_pause(ms: int) -> None:
    return None


def http_agent(server: ScriptedServer, **kwargs: int) -> HttpAgentsClient:
    return HttpAgentsClient(server.url, API_KEY, async_sleep=no_pause, **kwargs)


def test_ac15_no_first_frame_in_time_is_a_503_and_the_message_is_saved(
    api: Api, server: ScriptedServer, admin: Connection[DictRow]
) -> None:
    server.serve(
        Reply(200, chat_bytes("answer_length"), content_type="text/event-stream", chunked=True, delay_ms=1_500)
    )
    api.use(http_agent(server, first_frame_timeout_ms=300, total_timeout_ms=2_000))
    sent = api.send(api.cast.alicia)
    assert sent.status == 503 and sent.problem is not None and sent.problem["code"] == "agent_unavailable"
    assert [r["role"] for r in stored(admin, sent.problem["conversation_id"])] == ["user"]


def test_ac15_a_stream_that_runs_past_the_total_budget_is_cut_with_a_timeout_error(
    api: Api, server: ScriptedServer, admin: Connection[DictRow]
) -> None:
    pieces = [b'event: token\ndata: {"delta":"x"}\n\n'] * 60
    server.serve(Reply(200, content_type="text/event-stream", chunked=True, pieces=pieces, chunk_delay_ms=100))
    api.use(http_agent(server, first_frame_timeout_ms=600, total_timeout_ms=600))
    sent = api.send(api.cast.alicia)
    assert sent.status == 200 and sent.terminal.name == "error" and sent.terminal.data["code"] == "timeout"
    assert 1 <= len(sent.of("token")) < 12
    _, assistant = stored(admin, sent.conversation_id)
    assert assistant["status"] == "error" and assistant["content"] == "x" * len(sent.of("token"))


# --- AC-16 · Tope por hora ------------------------------------------------------------------------------------------------------------


def test_ac16_the_message_over_the_limit_is_a_429_with_retry_after_and_leaves_no_trace(
    api: Api, admin: Connection[DictRow], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MESSAGES_PER_HOUR", 3)
    api.script("answer_length", "answer_length", "answer_length", "answer_length")
    alicia = api.cast.alicia
    first = api.send(alicia)
    api.send(alicia, "dos", first.conversation_id)
    api.send(alicia, "tres", first.conversation_id)
    refused = api.send(alicia, "cuatro", first.conversation_id)
    assert refused.status == 429 and refused.problem is not None and refused.problem["code"] == "chat_rate_limited"
    assert (
        1 <= int(refused.headers["retry-after"]) <= 3_600 and int(refused.headers["retry-after"]) > 3_000
    )  # los tres entraron hace un instante
    assert len(api.agent.chat_calls) == 3  # no se llamó al agente
    assert [r["role"] for r in stored(admin, first.conversation_id)] == [
        "user",
        "assistant",
    ] * 3  # el cuarto no se guardó
    new_conversation = api.send(alicia, "una nueva")
    assert new_conversation.status == 429 and conversation_count(admin, alicia) == 1
    assert api.send(api.cast.beto).status == 200  # el tope es de cada persona


def test_ac16_retry_after_is_when_the_oldest_counted_message_leaves_the_hour(
    api: Api, admin: Connection[DictRow], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MESSAGES_PER_HOUR", 2)
    api.script("answer_length")
    first = api.send(api.cast.alicia)
    admin.execute(
        "insert into public.chat_messages (conversation_id, owner_id, role, content, created_at) "
        "values (%s, %s, 'user', 'antiguo', now() - interval '59 minutes 30 seconds')",
        (first.conversation_id, api.cast.alicia.id),
    )
    refused = api.send(api.cast.alicia, "uno más", first.conversation_id)
    assert (
        refused.status == 429 and 20 <= int(refused.headers["retry-after"]) <= 45
    )  # al más antiguo le quedan unos 30 s


def test_ac16_two_sends_at_the_limit_at_the_same_time_only_one_gets_through(
    api: Api, admin: Connection[DictRow], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MESSAGES_PER_HOUR", 1)
    api.script("answer_length", "answer_length")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda text: api.send(api.cast.alicia, text), ["a", "b"]))
    assert sorted(r.status for r in results) == [200, 429]
    assert conversation_count(admin, api.cast.alicia) == 1


# --- AC-17 · Validación ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("", "message_empty"),
        ("   ", "message_empty"),
        ("\n\t \n", "message_empty"),
        ("a" * 2_001, "message_too_long"),
        (" " + "a" * 2_001, "message_too_long"),
    ],
)
def test_ac17_an_empty_or_too_long_message_is_a_422_and_nothing_is_saved_or_asked(
    api: Api, admin: Connection[DictRow], content: str, code: str
) -> None:
    api.script("answer_length")
    sent = api.send(api.cast.alicia, content)
    assert sent.status == 422 and sent.problem is not None and sent.problem["code"] == code
    assert conversation_count(admin, api.cast.alicia) == 0 and not api.agent.chat_calls


def test_ac17_exactly_two_thousand_characters_is_fine_and_is_saved_without_the_edge_whitespace(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("answer_length")
    sent = api.send(api.cast.alicia, "  " + "a" * 2_000 + "  \n")
    assert sent.status == 200
    assert stored(admin, sent.conversation_id)[0]["content"] == "a" * 2_000


@pytest.mark.parametrize(
    "body", [{"content": "a" * 8_001}, {}, {"content": 5}, {"conversation_id": "no-es-uuid", "content": "hola"}]
)
def test_ac17_a_malformed_body_is_a_validation_error(api: Api, body: dict) -> None:  # type: ignore[type-arg]
    response = api.request("POST", "/api/chat", api.cast.alicia, json=body)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_ac17_a_conversation_that_does_not_exist_is_a_404_and_creates_nothing(
    api: Api, admin: Connection[DictRow]
) -> None:
    sent = api.send(api.cast.alicia, "hola", "00000000-0000-4000-8000-000000000042")
    assert sent.status == 404 and sent.problem is not None and sent.problem["code"] == "conversation_not_found"
    assert conversation_count(admin, api.cast.alicia) == 0


# --- AC-18 · Contenido que no es de fiar ----------------------------------------------------------------------------------------------


def test_ac18_html_and_scripts_travel_and_are_saved_as_plain_text_and_nothing_is_evaluated(
    api: Api, admin: Connection[DictRow]
) -> None:
    html = '<img src=x onerror=alert(1)> <script>alert("x")</script> [enlace](javascript:alert(1)) **negrita**'
    api.script(token_frames(html))
    sent = api.send(api.cast.alicia)
    assert sent.text == html and stored(admin, sent.conversation_id)[1]["content"] == html
    assert api.conversation(api.cast.alicia, sent.conversation_id).json()["messages"][1]["content"] == html


def test_ac18_a_citation_with_a_plain_http_url_is_kept_as_it_came_so_the_interface_decides_not_to_link_it(
    api: Api,
) -> None:
    api.script(
        frames_of(
            b'event: token\ndata: {"delta":"ver"}\n\n'
            b'event: citation\ndata: {"id":"1","title":"t","publisher":"p","url":"http://sitio.example.test/a","valid_as_of":null,"quote":null}\n\n'
            b'event: done\ndata: {"finish_reason":"stop","trace_id":"t"}\n\n'
        )
    )
    sent = api.send(api.cast.alicia)
    assert (
        sent.of("citation")[0].data["url"] == "http://sitio.example.test/a" and sent.terminal.data["has_source"] is True
    )


def test_ac18_an_over_long_answer_is_cut_at_the_limit_and_what_is_forwarded_is_what_is_saved(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script(token_frames("a" * 3_000, "b" * 3_000, "c" * 3_000, "d" * 10))
    sent = api.send(api.cast.alicia)
    assert len(sent.text) == limits.MAX_REPLY_CHARS and sent.text == "a" * 3_000 + "b" * 3_000 + "c" * 2_000
    assert sent.terminal.data["finish_reason"] == "length" and sent.terminal.data["status"] == "complete"
    assert stored(admin, sent.conversation_id)[1]["content"] == sent.text


def test_ac18_citations_are_capped_and_only_the_first_abstention_counts(api: Api) -> None:
    citation = b'event: citation\ndata: {"id":"%d","title":"t","publisher":"p","url":"https://x.example.test/a","valid_as_of":null,"quote":null}\n\n'
    body = b'event: token\ndata: {"delta":"x"}\n\n' + b"".join(citation % n for n in range(25))
    body += b'event: abstention\ndata: {"reason":"no_source","referral":"asesor"}\n\n'
    body += b'event: abstention\ndata: {"reason":"out_of_scope","referral":null}\n\n'
    body += b'event: done\ndata: {"finish_reason":"abstained","trace_id":"t"}\n\n'
    api.script(frames_of(body))
    sent = api.send(api.cast.alicia)
    assert len(sent.of("citation")) == limits.MAX_CITATIONS
    assert [e.data["reason"] for e in sent.of("abstention")] == ["no_source"]


def test_ac18_frames_after_the_terminal_one_are_ignored(api: Api) -> None:
    extra = frames_of(
        b'event: token\ndata: {"delta":"tarde"}\n\nevent: done\ndata: {"finish_reason":"stop","trace_id":"t2"}\n\n'
    )
    api.script([*frames("answer_with_citation"), *extra])
    sent = api.send(api.cast.alicia)
    assert (
        "tarde" not in sent.text
        and sent.names.count("done") == 1
        and sent.terminal.data["trace_id"] == "trc_synthetic_0101"
    )


def test_ac18_unknown_events_and_a_stream_with_garbage_after_done_through_the_real_http_client(
    api: Api, server: ScriptedServer
) -> None:
    pieces = [
        b"event: ping\ndata: lo-que-sea\n\n",
        b'event: token\ndata: {"delta":"hola"}\n\n',
        b": latido\n\n",
        b'event: done\ndata: {"finish_reason":"stop","trace_id":"trc_h"}\n\n',
        b'event: token\ndata: {"delta":"despues"}\n\n',
    ]
    server.serve(Reply(200, content_type="text/event-stream", chunked=True, pieces=pieces))
    api.use(http_agent(server))
    sent = api.send(api.cast.alicia)
    assert sent.names == ["start", "token", "done"] and sent.text == "hola"


def test_ac18_a_known_event_that_breaks_the_contract_ends_the_stream_with_a_fixed_error(
    api: Api, server: ScriptedServer, admin: Connection[DictRow]
) -> None:
    server.serve(
        Reply(
            200,
            content_type="text/event-stream",
            chunked=True,
            pieces=[
                b'event: token\ndata: {"delta":"bien"}\n\n',
                b'event: token\ndata: {"delta": 5, "secreto": "SECRETO"}\n\n',
            ],
        )
    )
    api.use(http_agent(server))
    sent = api.send(api.cast.alicia)
    assert (
        sent.names == ["start", "token", "error"]
        and sent.terminal.data["code"] == "agent_error"
        and "SECRETO" not in sent.raw
    )
    assert stored(admin, sent.conversation_id)[1]["content"] == "bien"
