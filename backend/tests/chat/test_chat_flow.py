"""AC-01 a AC-10 · El chat de punta a punta con la aplicación y la base de datos reales (SPEC-W-004 §7).

El agente es el simulado (ejemplos de `contracts/examples/chat/`) o un doble de `fakes.py`; la base de datos es la local.
"""

import uuid

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents.sse import frames_of
from cuadre.chat import rules
from tests.chat.conftest import QUESTION, Api, conversation_count, stored
from tests.chat.fakes import GatedAgent, frames
from tests.gestor.support import link
from tests.support import Pool

PLAIN = frames_of(
    b'event: token\ndata: {"delta":"Hola, "}\n\nevent: token\ndata: {"delta":"te cuento."}\n\nevent: done\ndata: {"finish_reason":"stop","trace_id":"trc_plain"}\n\n'
)


# --- AC-01 · Una pregunta con fuente --------------------------------------------------------------------------------------------------


def test_ac01_a_question_with_a_source_streams_saves_and_is_listed(api: Api, admin: Connection[DictRow]) -> None:
    api.script("answer_with_citation")
    sent = api.send(api.cast.alicia)

    assert sent.status == 200
    assert sent.headers["content-type"].startswith("text/event-stream")
    assert sent.headers["cache-control"] == "private, no-store" and sent.headers["x-accel-buffering"] == "no"
    assert sent.headers["x-request-id"]
    assert sent.names == ["start", "token", "token", "citation", "usage", "done"]
    assert sent.text == (
        "Si el cliente es una empresa de la UE con NIF-IVA válido, "
        "la factura va sin IVA y debe incluir la mención «Inversión del sujeto pasivo» [1]."
    )
    (citation,) = sent.of("citation")
    assert citation.data["publisher"] == "BOE" and citation.data["url"].startswith("https://www.boe.es/")
    assert sent.of("usage")[0].data == {"input_tokens": 2410, "output_tokens": 96}  # sin el coste: no sale del servidor

    done = sent.terminal
    assert done.name == "done" and done.data["status"] == "complete" and done.data["finish_reason"] == "stop"
    assert done.data["has_source"] is True and done.data["trace_id"] == "trc_synthetic_0101"
    assert done.data["message_id"] == str(sent.message_id)

    user_row, assistant_row = stored(admin, sent.conversation_id)
    assert (user_row["role"], user_row["status"], user_row["content"]) == ("user", "complete", QUESTION)
    assert str(user_row["id"]) == sent.of("start")[0].data["user_message_id"]
    assert assistant_row["id"] == sent.message_id and assistant_row["role"] == "assistant"
    assert assistant_row["content"] == sent.text and assistant_row["has_source"] is True
    assert assistant_row["citations"][0]["id"] == "1"

    (listed,) = api.conversations(api.cast.alicia)
    assert listed["id"] == str(sent.conversation_id) and listed["title"] == rules.title_of(QUESTION)
    assert api.conversations(api.cast.beto) == []


def test_a_second_message_goes_in_the_same_conversation_and_keeps_the_title(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("answer_with_citation", "answer_length")
    first = api.send(api.cast.alicia)
    second = api.send(api.cast.alicia, "¿Y a una de fuera de la UE?", first.conversation_id)
    assert second.conversation_id == first.conversation_id
    assert [r["role"] for r in stored(admin, first.conversation_id)] == ["user", "assistant", "user", "assistant"]
    (listed,) = api.conversations(api.cast.alicia)
    assert listed["title"] == rules.title_of(QUESTION)
    request = api.agent.chat_calls[-1].request
    assert [m.role for m in request.messages] == ["user", "assistant", "user"] and request.messages[
        -1
    ].content == "¿Y a una de fuera de la UE?"


# --- AC-02 · El flujo no se acumula ---------------------------------------------------------------------------------------------------


def test_ac02_the_first_events_arrive_before_the_agent_emits_the_rest(api: Api) -> None:
    agent = api.use(GatedAgent(frames("answer_with_citation"), gate_after=2))
    with api.client.stream(
        "POST", "/api/chat", headers=api.headers(api.cast.alicia), json={"conversation_id": None, "content": QUESTION}
    ) as response:
        assert response.status_code == 200
        lines = response.iter_lines()
        before: list[str] = []
        for line in lines:
            before.append(line)
            if before.count("event: token") == 2:
                break
        assert before[0] == "event: start" and not agent.gate.is_set()
        assert agent.reached_gate.wait(5) is True  # el servicio pidió el tercer frame y está esperando
        agent.gate.set()
        rest = [line for line in lines]
    assert [line for line in rest if line.startswith("event: ")] == ["event: citation", "event: usage", "event: done"]
    assert not agent.timed_out


# --- AC-03, AC-04 · Abstención y derivación -------------------------------------------------------------------------------------------


def test_ac03_a_professional_judgment_abstains_and_refers_to_an_adviser_without_a_gestor(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("abstention_professional")
    sent = api.send(api.cast.alicia, "¿Me conviene darme de alta en módulos?")
    (abstention,) = sent.of("abstention")
    assert abstention.data == {
        "reason": "professional_judgment",
        "referral": "asesor",
    }  # el agente dijo «gestor»; Alicia no tiene
    assert (
        sent.terminal.name == "done"
        and sent.terminal.data["status"] == "abstained"
        and sent.terminal.data["has_source"] is None
    )
    assert sent.terminal.data["finish_reason"] == "abstained"
    stored_abstention = stored(admin, sent.conversation_id)[1]["abstention"]
    assert stored_abstention == {"reason": "professional_judgment", "referral": "asesor"}
    detail = api.conversation(api.cast.alicia, sent.conversation_id).json()
    assert detail["messages"][1]["abstention"] == stored_abstention and detail["messages"][1]["status"] == "abstained"


def test_ac04_with_an_active_gestor_the_referral_is_the_gestor(api: Api, app_pool: Pool) -> None:
    link(app_pool, api.cast.alicia, api.cast.gina)
    api.script("abstention_professional")
    sent = api.send(api.cast.alicia)
    assert sent.of("abstention")[0].data["referral"] == "gestor"
    assert api.agent.chat_calls[-1].request.user_context.has_gestor is True


@pytest.mark.parametrize(
    ("fixture", "reason", "referral"),
    [("abstention_no_source", "no_source", "asesor"), ("abstention_out_of_scope", "out_of_scope", None)],
)
def test_the_other_abstentions_keep_their_reason_and_referral(
    api: Api, fixture: str, reason: str, referral: str | None
) -> None:
    api.script(fixture)
    sent = api.send(api.cast.alicia)
    assert sent.of("abstention")[0].data == {"reason": reason, "referral": referral}
    assert sent.terminal.data["status"] == "abstained"


# --- AC-05, AC-06 · Sin fuente y herramientas -----------------------------------------------------------------------------------------


def test_ac05_an_answer_without_citations_or_tools_is_saved_as_without_source(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script(PLAIN)
    sent = api.send(api.cast.alicia)
    assert sent.terminal.data["has_source"] is False and sent.terminal.data["status"] == "complete"
    assert stored(admin, sent.conversation_id)[1]["has_source"] is False
    assert api.conversation(api.cast.alicia, sent.conversation_id).json()["messages"][1]["has_source"] is False


def test_ac06_tool_calls_are_forwarded_and_a_finished_one_counts_as_a_source(api: Api) -> None:
    api.script("answer_with_tool")
    sent = api.send(api.cast.alicia)
    assert [e.data["status"] for e in sent.of("tool_call")] == ["started", "finished"]
    assert sent.terminal.data["has_source"] is True


def test_ac06_a_failed_tool_does_not_break_the_stream_and_an_error_frame_ends_it_with_a_fixed_text(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("error_tool")
    sent = api.send(api.cast.alicia)
    assert [e.data["status"] for e in sent.of("tool_call")] == ["started", "failed"]
    error = sent.terminal
    assert error.name == "error" and error.data["code"] == "tool_error"
    assert (
        error.data["message"] == rules.BROWSER_ERRORS["tool_error"] and "No se pudieron" not in error.data["message"]
    )  # no es el texto del agente
    assert stored(admin, sent.conversation_id)[1]["status"] == "error"


# --- AC-08 · Valoración ---------------------------------------------------------------------------------------------------------------


def answered(api: Api) -> tuple[uuid.UUID, uuid.UUID]:
    api.script("answer_with_citation")
    sent = api.send(api.cast.alicia)
    return sent.conversation_id, sent.message_id


def test_ac08_a_person_rates_an_answer_and_changes_their_mind(api: Api) -> None:
    conversation, message = answered(api)
    assert api.rate(api.cast.alicia, message, "up").json() == {
        "message_id": str(message),
        "rating": "up",
        "reason": None,
    }
    assert api.conversation(api.cast.alicia, conversation).json()["messages"][1]["rating"] == "up"
    assert api.rate(api.cast.alicia, message, "down", "no_source").json()["reason"] == "no_source"
    detail = api.conversation(api.cast.alicia, conversation).json()["messages"][1]
    assert (detail["rating"], detail["reason"]) == ("down", "no_source")
    assert api.conversation(api.cast.alicia, conversation).json()["messages"][0]["rating"] is None


@pytest.mark.parametrize(("rating", "reason"), [("down", None), ("up", "other"), ("down", "malo"), ("meh", None)])
def test_a_rating_without_its_reason_or_with_an_unknown_one_is_a_422(api: Api, rating: str, reason: str | None) -> None:
    _, message = answered(api)
    response = api.rate(api.cast.alicia, message, rating, reason)
    assert response.status_code == 422 and response.headers["content-type"].startswith("application/problem+json")


def test_ac08_only_the_assistants_answers_of_your_own_can_be_rated(api: Api, admin: Connection[DictRow]) -> None:
    conversation, message = answered(api)
    user_message = stored(admin, conversation)[0]["id"]
    for target, person in ((user_message, api.cast.alicia), (message, api.cast.beto), (uuid.uuid4(), api.cast.alicia)):
        response = api.rate(person, target, "up")
        assert response.status_code == 404 and response.json()["code"] == "message_not_found"
    assert admin.execute(
        "select count(*) as n from public.chat_feedback where owner_id = %s", (api.cast.alicia.id,)
    ).fetchone() == {"n": 0}


# --- AC-09, AC-10 · Historial y borrado -----------------------------------------------------------------------------------------------


def test_ac09_the_list_goes_by_last_activity_and_a_conversation_reopens_as_it_was_saved(api: Api) -> None:
    api.script("answer_with_citation", "abstention_no_source", "answer_length")
    first = api.send(api.cast.alicia, "Primera pregunta")
    second = api.send(api.cast.alicia, "Segunda pregunta")
    api.send(
        api.cast.alicia, "Más sobre la primera", first.conversation_id
    )  # la primera conversación vuelve a ser la más reciente
    listed = api.conversations(api.cast.alicia)
    assert [c["id"] for c in listed] == [str(first.conversation_id), str(second.conversation_id)]
    assert [c["title"] for c in listed] == ["Primera pregunta", "Segunda pregunta"]

    detail = api.conversation(api.cast.alicia, first.conversation_id)
    assert detail.status_code == 200 and detail.headers["cache-control"] == "private, no-store"
    body = detail.json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assistant = body["messages"][1]
    assert (
        assistant["citations"][0]["publisher"] == "BOE"
        and assistant["has_source"] is True
        and assistant["trace_id"] == "trc_synthetic_0101"
    )
    assert assistant["content"].startswith("Si el cliente es una empresa de la UE")


def test_ac10_deleting_a_conversation_takes_its_messages_and_ratings_and_leaves_the_others(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("answer_with_citation", "answer_length")
    keep = api.send(api.cast.alicia, "Esta se queda")
    gone = api.send(api.cast.alicia, "Esta se borra")
    assert api.rate(api.cast.alicia, gone.message_id, "up").status_code == 200
    response = api.request("DELETE", f"/api/chat/conversations/{gone.conversation_id}", api.cast.alicia)
    assert (
        response.status_code == 204
        and response.content == b""
        and response.headers["cache-control"] == "private, no-store"
    )
    assert stored(admin, gone.conversation_id) == []
    assert admin.execute(
        "select count(*) as n from public.chat_feedback where message_id = %s", (gone.message_id,)
    ).fetchone() == {"n": 0}
    assert len(stored(admin, keep.conversation_id)) == 2
    assert api.conversation(api.cast.alicia, gone.conversation_id).status_code == 404
    assert (
        api.request("DELETE", f"/api/chat/conversations/{gone.conversation_id}", api.cast.alicia).json()["code"]
        == "conversation_not_found"
    )
    assert [c["id"] for c in api.conversations(api.cast.alicia)] == [str(keep.conversation_id)]


# --- AC-11 · Aislamiento (por la API) -------------------------------------------------------------------------------------------------


def test_ac11_nobody_sees_opens_writes_in_or_deletes_the_conversation_of_somebody_else(
    api: Api, admin: Connection[DictRow]
) -> None:
    api.script("answer_with_citation", "answer_length")
    own = api.send(api.cast.alicia)
    beto = api.cast.beto
    assert api.conversations(beto) == []
    assert api.conversation(beto, own.conversation_id).status_code == 404
    assert api.request("DELETE", f"/api/chat/conversations/{own.conversation_id}", beto).status_code == 404
    intrusion = api.send(beto, "Hola", own.conversation_id)
    assert (
        intrusion.status == 404
        and intrusion.problem is not None
        and intrusion.problem["code"] == "conversation_not_found"
    )
    assert len(stored(admin, own.conversation_id)) == 2 and conversation_count(admin, beto) == 0
    assert api.rate(beto, own.message_id, "up").status_code == 404


# --- El agente se cierra siempre al terminar (no solo si el navegador corta) ----------------------------------------------------------


def test_the_agents_generator_is_closed_when_the_stream_ends_normally(api: Api) -> None:
    """El cliente HTTP real devuelve tras el frame `done`, pero el servicio deja de leer ahí: sin cerrar el generador, la conexión quedaría abierta."""
    agent = api.use(GatedAgent(frames("answer_with_citation"), gate_after=99))
    sent = api.send(api.cast.alicia)
    assert sent.terminal.name == "done"
    assert agent.closed_explicitly.is_set()  # lo cerró el servicio; no basta con que el recolector lo limpie después
