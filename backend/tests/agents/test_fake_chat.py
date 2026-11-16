"""AC-23 · El cliente simulado sirve los ejemplos de `contracts/examples/chat/` con el mismo lector que el cliente HTTP (SPEC-W-004 §5.4)."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from cuadre.agents import FakeAgentsClient
from cuadre.agents.errors import AgentsError, FailureCode
from cuadre.agents.fake import (
    CHAT_ERROR_FIXTURES,
    DEFAULT_CHAT_SEQUENCE,
    MAX_RECORDED_CALLS,
    FakeScriptExhausted,
    FakeUnknownFixture,
)
from cuadre.agents.sse import frames_of
from cuadre_contracts import ChatRequest
from tests.agents.support import CHAT_NAMES, chat_bytes, chat_request, collect_frames, event_names, example_request

TOKEN = "token-mcp-sintetico"


def say(text: str, *, earlier: str | None = None, tools: bool = False) -> ChatRequest:
    messages = [{"role": "user", "content": earlier}, {"role": "assistant", "content": "Vale."}] if earlier else []
    messages.append({"role": "user", "content": text})
    base = chat_request("chat" if tools else "chat_no_tools").model_dump(mode="json")
    return ChatRequest.model_validate({**base, "messages": messages})


def ask(client: FakeAgentsClient, request: ChatRequest | None = None) -> list[str]:
    return event_names(collect_frames(client.stream_chat(request or chat_request(), request_id="req-1")))


@pytest.mark.parametrize("name", CHAT_NAMES)
def test_every_example_is_served_as_the_frames_the_shared_reader_gets_from_it(name: str) -> None:
    served = collect_frames(FakeAgentsClient().stream_chat(say(f"hola [fixture:{name}]"), request_id="r"))
    assert [f.model_dump_json() for f in served] == [f.model_dump_json() for f in frames_of(chat_bytes(name))]
    assert served[-1].root.event in ("done", "error")


def test_the_default_order_is_the_one_in_the_spec_and_loops() -> None:
    client = FakeAgentsClient()
    names = [ask(client)[-1] for _ in range(len(DEFAULT_CHAT_SEQUENCE) * 2)]
    assert DEFAULT_CHAT_SEQUENCE == (
        "answer_with_citation",
        "abstention_professional",
        "answer_with_tool",
        "abstention_no_source",
        "abstention_out_of_scope",
        "answer_length",
    )
    assert names == ["done"] * 12
    firsts = []
    for name in DEFAULT_CHAT_SEQUENCE * 2:
        firsts.append(collect_frames(FakeAgentsClient(chat_script=[name]).stream_chat(chat_request(), request_id="r")))
    again = FakeAgentsClient()
    cycle = [collect_frames(again.stream_chat(chat_request(), request_id="r")) for _ in range(12)]
    assert [[f.model_dump_json() for f in c] for c in cycle] == [[f.model_dump_json() for f in c] for c in firsts]


def test_the_errors_never_come_out_of_the_default_cycle() -> None:
    assert set(CHAT_ERROR_FIXTURES).isdisjoint(DEFAULT_CHAT_SEQUENCE)
    client = FakeAgentsClient()
    for _ in range(len(DEFAULT_CHAT_SEQUENCE) * 3):
        assert "error" not in ask(client)


def test_the_marker_chooses_the_example_and_does_not_spend_a_turn() -> None:
    client = FakeAgentsClient()
    assert event_names(collect_frames(client.stream_chat(say("[fixture:abstention_out_of_scope]"), request_id="r")))[
        -3:
    ] == [
        "abstention",
        "usage",
        "done",
    ]
    first = ask(client)  # el ciclo sigue donde estaba: el primero de la secuencia
    assert first == event_names(frames_of(chat_bytes(DEFAULT_CHAT_SEQUENCE[0])))
    assert ask(client) == event_names(frames_of(chat_bytes(DEFAULT_CHAT_SEQUENCE[1])))


def test_only_the_marker_of_the_last_message_counts() -> None:
    client = FakeAgentsClient()
    frames = event_names(
        collect_frames(client.stream_chat(say("otra cosa", earlier="[fixture:error_tool]"), request_id="r"))
    )
    assert frames == event_names(frames_of(chat_bytes(DEFAULT_CHAT_SEQUENCE[0])))
    assert (
        event_names(collect_frames(client.stream_chat(say("[fixture:error_tool]", earlier="hola"), request_id="r")))[-1]
        == "error"
    )


def test_an_error_example_is_served_as_a_frame_not_raised() -> None:
    frames = collect_frames(FakeAgentsClient().stream_chat(say("[fixture:error_upstream]"), request_id="r"))
    assert event_names(frames) == ["error"] and frames[0].root.data.code == "upstream_error"  # type: ignore[union-attr]


def test_an_unknown_marker_is_a_test_failure_not_an_agent_failure() -> None:
    with pytest.raises(FakeUnknownFixture):
        collect_frames(FakeAgentsClient().stream_chat(say("[fixture:no_existe]"), request_id="r"))


@pytest.mark.parametrize(
    "text", ["[fixture:]", "[fixture:../extract/invoice_ok]", "[fixture:Answer_Length]", "[fixture: answer_length]"]
)
def test_text_that_is_not_a_well_formed_marker_is_an_ordinary_question_and_never_touches_the_disk(text: str) -> None:
    assert ask(FakeAgentsClient(), say(text)) == event_names(frames_of(chat_bytes(DEFAULT_CHAT_SEQUENCE[0])))


def test_a_script_is_served_in_order_and_fails_when_it_runs_out() -> None:
    boom = AgentsError(FailureCode.agents_unavailable, http_status=503, trace_id="trc_x")
    frames = frames_of(chat_bytes("abstention_no_source"))
    client = FakeAgentsClient(chat_script=["answer_length", boom, frames])
    assert ask(client)[-1] == "done"
    with pytest.raises(AgentsError) as caught:
        ask(client)
    assert (caught.value.code, caught.value.http_status, caught.value.trace_id) == (
        FailureCode.agents_unavailable,
        503,
        "trc_x",
    )
    assert ask(client) == event_names(frames)
    with pytest.raises(FakeScriptExhausted):
        ask(client)


def test_the_marker_wins_over_the_script_and_leaves_it_untouched() -> None:
    client = FakeAgentsClient(chat_script=["answer_length"])
    assert event_names(collect_frames(client.stream_chat(say("[fixture:error_tool]"), request_id="r")))[-1] == "error"
    assert ask(client) == event_names(frames_of(chat_bytes("answer_length")))


def test_each_call_gets_its_own_copies_of_the_frames() -> None:
    client = FakeAgentsClient(chat_script=["answer_with_citation", "answer_with_citation"])
    first = collect_frames(client.stream_chat(chat_request(), request_id="r"))
    first[0].root.data.delta = "MODIFICADO"  # type: ignore[union-attr]
    second = collect_frames(client.stream_chat(chat_request(), request_id="r"))
    assert second[0].root.data.delta != "MODIFICADO"  # type: ignore[union-attr]
    assert (
        collect_frames(
            FakeAgentsClient(chat_script=["answer_with_citation"]).stream_chat(chat_request(), request_id="r")
        )[0].root.data.delta
        != "MODIFICADO"
    )  # type: ignore[union-attr]


def test_the_user_token_goes_if_and_only_if_there_are_tools() -> None:
    client = FakeAgentsClient()
    with pytest.raises(ValueError, match="user_token"):
        collect_frames(client.stream_chat(chat_request("chat"), request_id="r"))  # con herramientas y sin token
    with pytest.raises(ValueError, match="user_token"):
        collect_frames(
            client.stream_chat(chat_request("chat_no_tools"), request_id="r", user_token=TOKEN)
        )  # sin herramientas y con token
    assert not client.chat_calls  # un descuido de programación no gasta turno ni se registra
    assert ask(client) == event_names(frames_of(chat_bytes(DEFAULT_CHAT_SEQUENCE[0])))  # y no consumió el primer turno
    collect_frames(client.stream_chat(chat_request("chat"), request_id="r", user_token=TOKEN))
    assert [c.had_user_token for c in client.chat_calls] == [False, True]


def test_the_calls_are_recorded_without_the_token_and_the_record_is_bounded() -> None:
    client = FakeAgentsClient()
    collect_frames(client.stream_chat(chat_request("chat"), request_id="req-77", user_token=TOKEN))
    [call] = client.chat_calls
    assert call.request_id == "req-77" and call.request.mcp_url is not None and call.had_user_token
    assert TOKEN not in repr(call)
    for index in range(MAX_RECORDED_CALLS + 10):
        ask(client, say(f"[fixture:answer_length] {index}"))
    assert len(client.chat_calls) == MAX_RECORDED_CALLS


def test_chat_and_extract_scripts_do_not_share_their_turns() -> None:
    client = FakeAgentsClient()
    client.extract_invoice(example_request(), request_id="r")
    ask(client)
    ask(client)
    second_extract = client.extract_invoice(example_request(), request_id="r")
    fresh = FakeAgentsClient()
    fresh.extract_invoice(example_request(), request_id="r")
    assert second_extract == fresh.extract_invoice(
        example_request(), request_id="r"
    )  # el segundo turno de lectura es el segundo de siempre
    assert len(client.calls) == 2 and len(client.chat_calls) == 2


def test_many_conversations_at_once_each_get_their_own_turn() -> None:
    client = FakeAgentsClient()

    def one(_: int) -> str:
        return "|".join(event_names(asyncio.run(_collect(client))))

    async def _collect(c: FakeAgentsClient) -> list:  # type: ignore[type-arg]
        return [f async for f in c.stream_chat(chat_request(), request_id="r")]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, range(24)))
    expected = ["|".join(event_names(frames_of(chat_bytes(n)))) for n in DEFAULT_CHAT_SEQUENCE]
    assert sorted(results) == sorted(expected * 4)  # 24 turnos = cuatro vueltas completas, ninguno repetido ni perdido


def test_closing_the_generator_early_is_clean() -> None:
    async def run() -> None:
        stream = FakeAgentsClient().stream_chat(chat_request(), request_id="r")
        first = await anext(stream)
        assert first.root.event == "token"
        await stream.aclose()
        with pytest.raises(StopAsyncIteration):
            await anext(stream)

    asyncio.run(run())
