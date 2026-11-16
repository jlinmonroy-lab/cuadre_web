"""AC-19, AC-20, AC-21, AC-23 · Lo que recibe el agente, lo que no sale del servidor, los registros y el contrato público (SPEC-W-004 §7)."""

import json
import uuid

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.chat import limits
from tests.agents.support import captured_logs, rendered
from tests.chat.conftest import QUESTION, Api, stored
from tests.chat.fakes import BrokenAgent
from tests.gestor.support import link
from tests.rules.paths import REPO
from tests.support import Pool, apply_scenario

# --- AC-19 · La petición al agente ----------------------------------------------------------------------------------------------------


def test_ac19_the_agent_receives_the_context_the_user_context_and_no_tools(api: Api) -> None:
    api.script("answer_with_citation")
    sent = api.send(api.cast.alicia)
    (call,) = api.agent.chat_calls
    request = call.request
    assert request.conversation_id == sent.conversation_id and request.locale == "es-ES"
    assert [(m.role, m.content) for m in request.messages] == [("user", QUESTION)]
    assert request.user_context.role == "usuario" and request.user_context.has_gestor is False
    assert request.user_context.current_date.isoformat() == "2026-11-16"  # el reloj de la aplicación, en Europe/Madrid
    assert request.mcp_url is None and call.had_user_token is False
    assert call.request_id == sent.headers["x-request-id"]


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("baseline", False), ("pending", False), ("declined", False), ("revoked", False), ("active", True)],
)
def test_ac19_has_gestor_is_true_only_with_an_active_link(
    api: Api, app_pool: Pool, scenario: str, expected: bool
) -> None:
    apply_scenario(app_pool, api.cast, scenario)
    api.script("answer_length")
    api.send(api.cast.alicia)
    assert api.agent.chat_calls[-1].request.user_context.has_gestor is expected


def test_ac19_an_active_link_of_somebody_else_is_not_yours(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.beto, api.cast.gina)
    api.script("answer_length")
    api.send(api.cast.alicia)
    assert api.agent.chat_calls[-1].request.user_context.has_gestor is False


def test_ac19_only_the_latest_fifty_messages_go_and_always_start_with_a_question(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("answer_length", "answer_length")
    first = api.send(api.cast.alicia, "pregunta 0")
    # Una historia larga, de hace dos días (para no contar en el tope por hora): 40 pares de pregunta y respuesta.
    for n in range(1, 41):
        for role, text in (("user", f"pregunta {n}"), ("assistant", f"respuesta {n}")):
            admin.execute(
                "insert into public.chat_messages (conversation_id, owner_id, role, content, finish_reason, created_at) "
                "values (%s, %s, %s, %s, %s, now() - interval '2 days' + make_interval(secs => %s))",
                (
                    first.conversation_id,
                    api.cast.alicia.id,
                    role,
                    text,
                    "stop" if role == "assistant" else None,
                    n * 2 + (role == "assistant"),
                ),
            )
    api.send(api.cast.alicia, "la última", first.conversation_id)
    messages = api.agent.chat_calls[-1].request.messages
    contents = [m.content for m in messages]
    # 83 filas en total (80 de la historia, y la pregunta 0, su respuesta y la nueva): van las 50 últimas y la primera tiene que ser una pregunta.
    assert 49 <= len(messages) <= limits.CONTEXT_MESSAGES and messages[0].role == "user" and contents[-1] == "la última"
    assert (
        contents[-3] == "pregunta 0" and "pregunta 1" not in contents and "pregunta 40" in contents
    )  # lo viejo se corta; lo reciente, no
    assert all(a.role != b.role for a, b in zip(messages, messages[1:], strict=False))  # alternan pregunta y respuesta


def test_ac19_failed_and_interrupted_answers_and_their_questions_do_not_go_back_to_the_agent(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("error_upstream", "answer_length", "answer_length")
    broken_one = api.send(api.cast.alicia, "pregunta que falló")
    assert broken_one.terminal.name == "error"
    ok = api.send(api.cast.alicia, "pregunta buena", broken_one.conversation_id)
    assert ok.terminal.name == "done"
    api.send(api.cast.alicia, "otra más", broken_one.conversation_id)
    assert [(m.role, m.content) for m in api.agent.chat_calls[-1].request.messages][0] == ("user", "pregunta buena")
    assert "pregunta que falló" not in [m.content for m in api.agent.chat_calls[-1].request.messages]
    assert [r["status"] for r in stored(admin, broken_one.conversation_id) if r["role"] == "assistant"] == [
        "error",
        "complete",
        "complete",
    ]


# --- AC-20 · Frontera ----------------------------------------------------------------------------------------------------------------


def test_ac20_nothing_secret_nor_the_agents_key_nor_the_session_token_reaches_the_browser(api: Api) -> None:
    api.script("answer_with_tool")
    sent = api.send(api.cast.alicia)
    wire = sent.raw + "\n".join(f"{k}: {v}" for k, v in sent.headers.items())
    for secret in (api.token(api.cast.alicia), "Bearer", "AGENTS_API_KEY", "X-User-Token", "mcp_url", "service_role"):
        assert secret not in wire
    assert "cost_eur" not in wire and "0.005000" not in wire  # el coste interno no sale del servidor


def test_ac20_the_chat_modules_import_no_llm_sdk_and_the_agent_package_does_not_import_the_chat() -> None:
    forbidden = ("anthropic", "openai", "google.generativeai", "cohere", "mistralai")
    sources = [
        *(REPO / "backend" / "src" / "cuadre" / "chat").glob("*.py"),
        REPO / "backend" / "src" / "cuadre" / "api" / "routes_chat.py",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert not any(f"import {name}" in text or f"from {name}" in text for name in forbidden), path.name
    for path in (REPO / "backend" / "src" / "cuadre" / "agents").glob("*.py"):
        imports = [
            line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(("import ", "from "))
        ]
        assert not [line for line in imports if "cuadre.chat" in line], path.name


# --- AC-21 · Registros sin contenido ------------------------------------------------------------------------------------------------


SECRET_QUESTION = "¿Debo declarar la factura privada de MARGARITA LOPEZ con NIF 12345678Z?"
SECRET_ANSWER = "El texto de esta respuesta no puede aparecer jamás en un registro"


def test_ac21_logs_carry_ids_codes_and_numbers_and_never_the_text(api: Api) -> None:
    body = (
        f'event: token\ndata: {{"delta":"{SECRET_ANSWER}"}}\n\n'
        'event: citation\ndata: {"id":"1","title":"Titulo secreto de la fuente","publisher":"BOE","url":"https://www.boe.es/secreto","valid_as_of":null,"quote":null}\n\n'
        'event: usage\ndata: {"input_tokens":120,"output_tokens":34,"cost_eur":"0.004200"}\n\n'
        'event: done\ndata: {"finish_reason":"stop","trace_id":"trc_log"}\n\n'
    )
    from cuadre.agents.sse import frames_of

    api.script(frames_of(body.encode()), "abstention_professional", "error_upstream")
    with captured_logs("cuadre") as records:
        ok = api.send(api.cast.alicia, SECRET_QUESTION)
        api.send(api.cast.alicia, SECRET_QUESTION, ok.conversation_id)
        api.send(api.cast.alicia, SECRET_QUESTION, ok.conversation_id)
    text = rendered(records)
    for needle in (
        SECRET_QUESTION,
        "MARGARITA",
        "12345678Z",
        SECRET_ANSWER,
        "Titulo secreto",
        "boe.es/secreto",
        "0.004200",
        "Te sugiero consultarlo",
        "servicio de lenguaje",
    ):
        assert needle not in text, needle

    streams = [r for r in records if r.getMessage() == "chat_stream"]
    assert len(streams) == 3
    first = streams[0].__dict__
    assert first["user_id"] == str(api.cast.alicia.id) and first["conversation_id"] == str(ok.conversation_id)
    assert (
        first["request_id"]
        and first["outcome"] == "complete"
        and first["finish_reason"] == "stop"
        and first["has_source"] is True
    )
    assert (
        (first["input_tokens"], first["output_tokens"], first["saved"]) == (120, 34, "saved")
        and first["duration_ms"] >= 0
        and first["frames"] == 4
    )
    assert [r.__dict__["outcome"] for r in streams] == ["complete", "abstained", "error"] and streams[
        2
    ].levelname == "WARNING"
    assert streams[2].__dict__["error_code"] == "agent_error"


def test_ac21_a_request_that_fails_before_the_stream_is_logged_without_text(api: Api) -> None:
    from cuadre.agents import AgentsError, FailureCode

    api.script(AgentsError(FailureCode.timeout))
    with captured_logs("cuadre") as records:
        sent = api.send(api.cast.alicia, SECRET_QUESTION)
    assert sent.status == 503
    text = rendered(records)
    assert SECRET_QUESTION not in text and "MARGARITA" not in text
    (record,) = [r for r in records if r.getMessage() == "chat_stream"]
    assert (
        record.__dict__["outcome"] == "timeout"
        and record.__dict__["saved"] == "not_started"
        and record.levelname == "WARNING"
    )


def test_ac21_an_unexpected_failure_in_the_middle_logs_the_exception_type_and_not_its_message(api: Api) -> None:
    api.use(BrokenAgent([], error=RuntimeError("DETALLE-INTERNO-SECRETO")))
    api.use(BrokenAgent(frames_of_one(), error=RuntimeError("DETALLE-INTERNO-SECRETO")))
    with captured_logs("cuadre") as records:
        api.send(api.cast.alicia, SECRET_QUESTION)
    text = rendered(records)
    assert "DETALLE-INTERNO" not in text and "RuntimeError" in text and SECRET_QUESTION not in text


def frames_of_one() -> list:  # type: ignore[type-arg]
    from cuadre.agents.sse import frames_of

    return frames_of(b'event: token\ndata: {"delta":"parte"}\n\n')[:1]


# --- AC-23 · El contrato público ---------------------------------------------------------------------------------------------------


def test_ac23_the_five_operations_are_in_the_openapi_and_the_stream_declares_no_event_stream_content() -> None:
    document = json.loads((REPO / "backend" / "openapi.json").read_text(encoding="utf-8"))
    operations = {
        (method.upper(), path): op["operationId"]
        for path, item in document["paths"].items()
        if path.startswith("/api/chat")
        for method, op in item.items()
    }
    assert operations == {
        ("POST", "/api/chat"): "stream_chat",
        ("GET", "/api/chat/conversations"): "list_chat_conversations",
        ("GET", "/api/chat/conversations/{conversation_id}"): "get_chat_conversation",
        ("DELETE", "/api/chat/conversations/{conversation_id}"): "delete_chat_conversation",
        ("PUT", "/api/chat/messages/{message_id}/feedback"): "rate_chat_message",
    }
    media_types: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "content" and isinstance(value, dict):
                    media_types.update(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(document)
    assert "text/event-stream" not in media_types  # `test_t214` solo admite JSON, problem+json y PDF
    assert "content" not in document["paths"]["/api/chat"]["post"]["responses"]["200"]
    assert {"401", "403", "404", "422", "429", "503"} <= set(document["paths"]["/api/chat"]["post"]["responses"])


def test_the_message_id_the_stream_announces_is_a_uuid_and_the_ids_are_all_different(api: Api) -> None:
    api.script("answer_length")
    sent = api.send(api.cast.alicia)
    start = sent.of("start")[0].data
    ids = {start["conversation_id"], start["user_message_id"], start["message_id"]}
    assert len(ids) == 3 and all(uuid.UUID(i) for i in ids)
