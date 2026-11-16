"""AC-01 a AC-06, AC-17, AC-18, AC-19 · Las reglas puras del chat (SPEC-W-004 §5.1): sin base de datos, red ni reloj."""

import json
import uuid
from datetime import date

import pytest

from cuadre.agents.sse import frames_of
from cuadre.chat import events, limits, rules
from cuadre.chat.types import ContextRow, Outcome

U = "user"
A = "assistant"


def row(role: str, content: str = "texto", status: str = "complete") -> ContextRow:
    return ContextRow(role, content, status)


def feed(body: str, *, has_gestor: bool = False) -> rules.ReplyAccumulator:
    reply = rules.ReplyAccumulator(has_gestor=has_gestor)
    for frame in frames_of(body.encode()):
        reply.accept(frame)
    return reply


def token(text: str) -> str:
    return f"event: token\ndata: {json.dumps({'delta': text})}\n\n"


DONE = 'event: done\ndata: {"finish_reason":"stop","trace_id":"trc_1"}\n\n'
CITATION = 'event: citation\ndata: {"id":"1","title":"t","publisher":"BOE","url":"https://www.boe.es/a","valid_as_of":"2026-09-01","quote":null}\n\n'
TOOL_STARTED = 'event: tool_call\ndata: {"name":"buscar_facturas","status":"started"}\n\n'
TOOL_FINISHED = 'event: tool_call\ndata: {"name":"buscar_facturas","status":"finished"}\n\n'
TOOL_FAILED = 'event: tool_call\ndata: {"name":"buscar_facturas","status":"failed"}\n\n'


# --- El mensaje de la persona ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", " ", "\n", "\t \r\n", "  ", " "])
def test_a_blank_message_is_empty(text: str) -> None:
    with pytest.raises(rules.MessageEmpty):
        rules.clean_message(text)


def test_the_message_is_trimmed_and_the_limit_counts_the_trimmed_text() -> None:
    assert rules.clean_message("  hola  \n") == "hola"
    assert rules.clean_message("a" * limits.MAX_MESSAGE_CHARS) == "a" * limits.MAX_MESSAGE_CHARS
    assert rules.clean_message(" " * 50 + "a" * limits.MAX_MESSAGE_CHARS + " " * 50) == "a" * limits.MAX_MESSAGE_CHARS
    with pytest.raises(rules.MessageTooLong):
        rules.clean_message("a" * (limits.MAX_MESSAGE_CHARS + 1))


def test_the_limit_is_read_when_called_so_it_can_be_changed_in_one_place(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_MESSAGE_CHARS", 5)
    assert rules.clean_message("12345") == "12345"
    with pytest.raises(rules.MessageTooLong):
        rules.clean_message("123456")


def test_internal_whitespace_and_accents_are_kept_in_the_message() -> None:
    assert rules.clean_message("  ¿Qué   IVA\naplico? ") == "¿Qué   IVA\naplico?"


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("Hola", "Hola"),
        (
            "  ¿Qué mención lleva una factura\n a una empresa alemana?  ",
            "¿Qué mención lleva una factura a una empresa alemana?",
        ),
        ("a" * 60, "a" * 60),
        (
            "palabra " * 20,
            "palabra palabra palabra palabra palabra palabra palabra",
        ),  # corta entre palabras, no por la mitad
        ("a" * 61, "a" * 60),  # una sola palabra larga: no hay dónde cortar, se corta en seco
        ("0123456789 " * 5 + "0123456789 extra", "0123456789 0123456789 0123456789 0123456789 0123456789"),
        ("x" * 59 + " yyy", "x" * 59),  # el corte caería a media palabra: se queda en la palabra anterior
        ("x" * 60 + " yyy", "x" * 60),  # el corte cae justo al final de una palabra: se conserva
    ],
)
def test_the_title_is_sixty_characters_in_one_line_without_cutting_a_word(text: str, title: str) -> None:
    assert rules.title_of(text) == title
    assert len(rules.title_of(text)) <= limits.TITLE_CHARS and "\n" not in rules.title_of(text)


# --- El contexto que va al agente --------------------------------------------------------------------------------------------------------


def test_the_context_is_the_conversation_in_order_ending_with_the_new_question() -> None:
    rows = [row(U, "p1"), row(A, "r1"), row(U, "p2")]
    assert rules.context_for_agent(rows) == [
        {"role": "user", "content": "p1"},
        {"role": "assistant", "content": "r1"},
        {"role": "user", "content": "p2"},
    ]


@pytest.mark.parametrize("status", ["error", "interrupted"])
def test_an_answer_that_failed_or_was_cut_does_not_go_back_and_takes_its_question_with_it(status: str) -> None:
    rows = [row(U, "p1"), row(A, "r1 a medias", status), row(U, "p2"), row(A, "r2"), row(U, "p3")]
    assert [m["content"] for m in rules.context_for_agent(rows)] == ["p2", "r2", "p3"]


def test_an_abstention_is_part_of_the_conversation() -> None:
    rows = [row(U, "p1"), row(A, "no puedo", "abstained"), row(U, "p2")]
    assert [m["content"] for m in rules.context_for_agent(rows)] == ["p1", "no puedo", "p2"]


def test_a_question_left_without_an_answer_is_dropped_but_the_new_one_always_stays() -> None:
    rows = [row(U, "repetida"), row(U, "repetida"), row(U, "repetida")]
    assert [m["content"] for m in rules.context_for_agent(rows)] == ["repetida"]
    assert rules.context_for_agent([row(U, "sola")]) == [{"role": "user", "content": "sola"}]


def test_an_empty_answer_does_not_count() -> None:
    assert [m["content"] for m in rules.context_for_agent([row(U, "p1"), row(A, "  "), row(U, "p2")])] == ["p2"]


def test_at_most_fifty_messages_and_the_first_is_always_a_question() -> None:
    rows = []
    for n in range(40):
        rows += [row(U, f"p{n}"), row(A, f"r{n}")]
    rows.append(row(U, "nueva"))  # 81 filas
    context = rules.context_for_agent(rows)
    assert (
        len(context) == 49 and context[0]["role"] == "user" and context[-1]["content"] == "nueva"
    )  # la fila 32 era una respuesta: se salta
    assert context[0]["content"] == "p16"
    # Con pregunta y respuesta alternas, la primera y la última son preguntas: el máximo real es 49 (el contrato admite 50).
    exact = rules.context_for_agent([row(U, "a"), row(A, "b")] * 24 + [row(U, "nueva")])
    assert len(exact) == 49 and exact[0]["role"] == "user" and len(exact) <= limits.CONTEXT_MESSAGES


def test_the_last_row_must_be_the_new_question() -> None:
    for bad in ([], [row(A, "r")], [row(U, "p"), row(A, "r")]):
        with pytest.raises(ValueError):
            rules.context_for_agent(bad)


def test_the_request_has_no_tools_and_says_who_asks_and_what_day_it_is() -> None:
    conversation = uuid.uuid4()
    request = rules.build_request(conversation, [row(U, "hola")], has_gestor=True, today=date(2026, 11, 16))
    assert request.conversation_id == conversation and request.locale == "es-ES" and request.mcp_url is None
    assert (request.user_context.role, request.user_context.has_gestor, request.user_context.current_date) == (
        "usuario",
        True,
        date(2026, 11, 16),
    )
    assert [(m.role, m.content) for m in request.messages] == [("user", "hola")]


# --- La respuesta que va llegando -------------------------------------------------------------------------------------------------------


def test_the_text_citations_and_usage_are_gathered_and_forwarded() -> None:
    body = (
        token("Hola, ")
        + token("mundo")
        + CITATION
        + 'event: usage\ndata: {"input_tokens":10,"output_tokens":3,"cost_eur":"0.001000"}\n\n'
        + DONE
    )
    reply = rules.ReplyAccumulator(has_gestor=False)
    forwarded = [event for frame in frames_of(body.encode()) for event in reply.accept(frame)]
    assert [name for name, _ in forwarded] == ["token", "token", "citation", "usage"]
    assert dict(forwarded)["usage"] == {"input_tokens": 10, "output_tokens": 3}  # sin el coste
    assert reply.text == "Hola, mundo" and reply.citations[0]["publisher"] == "BOE" and reply.terminal == "done"
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (10, 3) and reply.trace_id == "trc_1"


def test_empty_tokens_are_not_forwarded() -> None:
    reply = rules.ReplyAccumulator(has_gestor=False)
    assert reply.accept(frames_of(token("").encode())[0]) == [] and reply.text == ""


def test_nothing_is_accepted_after_the_terminal_frame() -> None:
    reply = feed(token("a") + DONE)
    late = frames_of((token("tarde") + CITATION).encode())
    assert [reply.accept(frame) for frame in late] == [[], []] and reply.text == "a" and reply.citations == []


def test_the_text_is_cut_at_the_limit_and_what_is_forwarded_is_what_is_kept() -> None:
    reply = rules.ReplyAccumulator(has_gestor=False)
    forwarded: list[str] = []
    for frame in frames_of((token("a" * 5_000) + token("b" * 5_000) + token("c")).encode()):
        forwarded += [data["delta"] for name, data in reply.accept(frame) if name == "token"]
    assert "".join(forwarded) == reply.text == "a" * 5_000 + "b" * 3_000 and reply.truncated
    assert forwarded == ["a" * 5_000, "b" * 3_000]  # ni un trozo vacío cuando ya no cabe nada
    assert len(reply.text) == limits.MAX_REPLY_CHARS


def test_a_cut_answer_that_the_agent_closed_as_stop_is_saved_as_length() -> None:
    reply = feed(token("a" * 9_000) + DONE)
    assert reply.outcome() == Outcome("complete", "length", False)


def test_at_most_twenty_citations() -> None:
    reply = feed(CITATION * 25 + DONE)
    assert len(reply.citations) == limits.MAX_CITATIONS


def test_the_first_abstention_wins() -> None:
    body = (
        'event: abstention\ndata: {"reason":"no_source","referral":"asesor"}\n\n'
        'event: abstention\ndata: {"reason":"out_of_scope","referral":null}\n\n'
        'event: done\ndata: {"finish_reason":"abstained","trace_id":"t"}\n\n'
    )
    assert feed(body).abstention == {"reason": "no_source", "referral": "asesor"}


@pytest.mark.parametrize(
    ("referral", "has_gestor", "expected"),
    [
        ("gestor", True, "gestor"),
        ("gestor", False, "asesor"),
        ("asesor", True, "asesor"),
        ("asesor", False, "asesor"),
        (None, True, None),
        (None, False, None),
    ],
)
def test_the_referral_depends_on_whether_the_person_has_a_gestor(
    referral: str | None, has_gestor: bool, expected: str | None
) -> None:
    assert rules.referral_for(referral, has_gestor) == expected
    body = f'event: abstention\ndata: {{"reason":"professional_judgment","referral":{json.dumps(referral)}}}\n\n{DONE}'
    if referral is not None:
        assert feed(body, has_gestor=has_gestor).abstention == {"reason": "professional_judgment", "referral": expected}


def test_a_tool_name_is_cut_to_a_sane_length() -> None:
    long_name = "x" * 500
    reply = rules.ReplyAccumulator(has_gestor=False)
    (event,) = reply.accept(
        frames_of(f'event: tool_call\ndata: {{"name":"{long_name}","status":"started"}}\n\n'.encode())[0]
    )
    assert len(event[1]["name"]) == limits.MAX_TOOL_NAME_CHARS


# --- Cómo terminó ------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (token("a") + DONE, Outcome("complete", "stop", False)),
        (token("a") + CITATION + DONE, Outcome("complete", "stop", True)),
        (token("a") + TOOL_STARTED + TOOL_FINISHED + DONE, Outcome("complete", "stop", True)),
        (token("a") + TOOL_STARTED + TOOL_FAILED + DONE, Outcome("complete", "stop", False)),
        (
            token("a") + TOOL_STARTED + DONE,
            Outcome("complete", "stop", False),
        ),  # una herramienta que no terminó no es una fuente
        (
            token("a") + CITATION + 'event: done\ndata: {"finish_reason":"length","trace_id":"t"}\n\n',
            Outcome("complete", "length", True),
        ),
        (
            token("a") + 'event: done\ndata: {"finish_reason":"abstained","trace_id":"t"}\n\n',
            Outcome("abstained", "abstained", None),
        ),
        (
            token("a") + 'event: abstention\ndata: {"reason":"no_source","referral":"asesor"}\n\n' + DONE,
            Outcome("abstained", "abstained", None),  # una abstención manda aunque el `done` diga `stop`
        ),
        (
            token("a") + 'event: done\ndata: {"finish_reason":"error","trace_id":"t"}\n\n',
            Outcome("error", "error", None, "agent_error"),
        ),
        (token("a"), Outcome("interrupted", None, None)),
        ("", Outcome("interrupted", None, None)),
    ],
)
def test_how_an_answer_ends(body: str, expected: Outcome) -> None:
    assert feed(body).outcome() == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("unauthorized", "agent_unavailable"),
        ("invalid_request", "agent_unavailable"),
        ("upstream_error", "agent_error"),
        ("tool_error", "tool_error"),
        ("timeout", "timeout"),
    ],
)
def test_an_error_frame_of_the_agent_becomes_one_of_our_fixed_codes(code: str, expected: str) -> None:
    reply = feed(token("parte") + f'event: error\ndata: {{"code":"{code}","message":"TEXTO DEL AGENTE"}}\n\n')
    assert reply.terminal == "error" and reply.outcome() == Outcome("error", "error", None, expected)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("timeout", "timeout"),
        ("upstream_error", "agent_error"),
        ("invalid_response", "agent_error"),
        ("agents_unavailable", "agent_unavailable"),
        ("internal", "agent_unavailable"),
        ("lo-que-sea", "agent_unavailable"),
    ],
)
def test_a_failure_of_the_agents_client_becomes_one_of_our_fixed_codes(failure: str, expected: str) -> None:
    assert rules.error_code_for_failure(failure) == expected
    reply = feed(token("parte"))
    reply.fail(expected)
    assert reply.outcome() == Outcome("error", "error", None, expected) and reply.text == "parte"


def test_every_code_the_browser_can_see_has_a_fixed_spanish_text() -> None:
    assert set(rules.BROWSER_ERRORS) == {"agent_unavailable", "agent_error", "tool_error", "timeout", "unavailable"}
    assert all(text.endswith(".") and len(text) > 20 for text in rules.BROWSER_ERRORS.values())


def test_the_terminal_event_carries_the_message_id_and_never_the_text_of_the_agent() -> None:
    message = uuid.uuid4()
    done = rules.terminal_event(Outcome("complete", "stop", True), message_id=message, trace_id="trc_9")
    assert done == (
        "done",
        {
            "finish_reason": "stop",
            "trace_id": "trc_9",
            "message_id": str(message),
            "has_source": True,
            "status": "complete",
        },
    )
    error = rules.terminal_event(Outcome("error", "error", None, "timeout"), message_id=message, trace_id="")
    assert error == (
        "error",
        {"code": "timeout", "message": rules.BROWSER_ERRORS["timeout"], "message_id": str(message)},
    )
    odd = rules.terminal_event(Outcome("error", "error", None, "algo-raro"), message_id=message, trace_id="")
    assert odd[1]["code"] == "agent_error"
    assert rules.unavailable_event(message)[1]["code"] == "unavailable"


# --- Los eventos hacia el navegador ----------------------------------------------------------------------------------------------------


def test_an_event_is_one_data_line_even_if_the_text_has_line_breaks() -> None:
    payload = events.encode(("token", {"delta": "línea 1\nlínea 2\r\ndata: falso\n\nevent: done"}))
    text = payload.decode("utf-8")
    assert text.startswith("event: token\ndata: {") and text.endswith("}\n\n") and text.count("\n") == 3
    assert (
        json.loads(text.split("\n")[1].removeprefix("data: "))["delta"]
        == "línea 1\nlínea 2\r\ndata: falso\n\nevent: done"
    )
    assert (
        "á" not in events.encode(("x", {"v": "a"})).decode()
        and "é" in events.encode(("token", {"delta": "é"})).decode()
    )  # UTF-8 sin escapar
