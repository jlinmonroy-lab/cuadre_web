"""AC-18, AC-23 · El lector de `text/event-stream` (SPEC-W-004 §5.4, D-10): trocea con topes, descarta lo desconocido y valida con el contrato."""

import importlib.util
import json

import pytest

from cuadre.agents.sse import (
    KNOWN_EVENTS,
    InvalidFrame,
    RawEvent,
    SseParser,
    SseProtocolError,
    decode_frame,
    frames_of,
    is_terminal,
)
from tests.agents.support import CHAT_NAMES, chat_bytes
from tests.rules.paths import REPO


def events_of(*chunks: bytes) -> list[RawEvent]:
    parser = SseParser()
    events: list[RawEvent] = []
    for chunk in chunks:
        events += parser.feed(chunk)
    return events + parser.finish()


def whole(name: str) -> list[RawEvent]:
    return events_of(chat_bytes(name))


# --- El troceado de la red no cambia lo que se lee ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", CHAT_NAMES)
def test_every_way_of_cutting_the_stream_in_two_gives_the_same_events(name: str) -> None:
    payload = chat_bytes(name)
    expected = whole(name)
    assert expected, name
    for cut in range(len(payload) + 1):
        assert events_of(payload[:cut], payload[cut:]) == expected, (name, cut)


@pytest.mark.parametrize("name", CHAT_NAMES)
def test_one_byte_at_a_time_gives_the_same_events(name: str) -> None:
    payload = chat_bytes(name)
    assert events_of(*(payload[i : i + 1] for i in range(len(payload)))) == whole(name)


@pytest.mark.parametrize("name", CHAT_NAMES)
@pytest.mark.parametrize("eol", [b"\r\n", b"\r"])
def test_crlf_and_lone_cr_line_ends_give_the_same_events(name: str, eol: bytes) -> None:
    payload = chat_bytes(name).replace(b"\n", eol)
    assert events_of(payload) == whole(name)
    assert events_of(*(payload[i : i + 1] for i in range(len(payload)))) == whole(name), (
        "un `\\r` al final de un trozo espera al siguiente"
    )


def test_a_multi_byte_character_split_between_two_chunks_is_not_broken() -> None:
    payload = 'event: token\ndata: {"delta":"Inversión «sujeto pasivo» €"}\n\n'.encode()
    expected = events_of(payload)
    assert "«sujeto pasivo» €" in expected[0].data
    for cut in range(len(payload) + 1):
        assert events_of(payload[:cut], payload[cut:]) == expected, cut


# --- Qué es un evento ---------------------------------------------------------------------------------------------------------------------


def test_comments_heartbeats_and_unknown_fields_are_ignored() -> None:
    payload = b": ping\n\nid: 7\nretry: 3000\nevent: token\n: otro comentario\ndata: {}\nfoo: bar\n\n"
    assert events_of(payload) == [RawEvent("token", "{}")]


def test_a_heartbeat_between_events_does_not_split_or_create_one() -> None:
    assert events_of(b"event: a\ndata: 1\n\n: ping\n\n: ping\n\nevent: b\ndata: 2\n\n") == [
        RawEvent("a", "1"),
        RawEvent("b", "2"),
    ]


def test_data_on_several_lines_is_joined_with_newlines() -> None:
    assert events_of(b"event: x\ndata: uno\ndata: dos\ndata:\ndata: cuatro\n\n") == [
        RawEvent("x", "uno\ndos\n\ncuatro")
    ]


def test_a_single_leading_space_after_the_colon_is_dropped_and_no_more() -> None:
    assert events_of(b"event:x\ndata:  dos espacios\n\n") == [RawEvent("x", " dos espacios")]


def test_an_event_without_data_is_not_an_event_and_does_not_leak_its_name_into_the_next() -> None:
    assert events_of(b"event: solo-nombre\n\nevent: b\ndata: 1\n\n") == [RawEvent("b", "1")]


def test_an_event_without_a_name_is_called_message() -> None:
    assert events_of(b"data: 1\n\n") == [RawEvent("message", "1")]


def test_a_lone_carriage_return_at_the_very_end_is_a_complete_line_end_once_the_stream_closes() -> None:
    parser = SseParser()
    assert parser.feed(b"event: a\rdata: 1\r\r") == []  # el último `\r` podría ser el principio de `\r\n`
    assert parser.finish() == [RawEvent("a", "1")]
    assert not parser.pending
    assert SseParser().finish() == []


def test_blank_lines_alone_are_nothing() -> None:
    assert events_of(b"\n\n\r\n\n") == []


def test_pending_tells_whether_something_was_left_unfinished() -> None:
    parser = SseParser()
    assert not parser.pending
    parser.feed(b"event: token\n")
    assert parser.pending  # el nombre sin su evento
    parser.feed(b"data: {}\n")
    assert parser.pending  # el evento aún no se cerró con una línea en blanco
    assert parser.feed(b"\n") == [RawEvent("token", "{}")]
    assert not parser.pending
    parser.feed(b"data: sin termin")
    assert parser.pending  # una línea a medias


# --- Topes y entrada malformada ---------------------------------------------------------------------------------------------------------------


def test_a_line_exactly_at_the_limit_is_fine_and_one_byte_more_is_not() -> None:
    at_limit = b"data: " + b"a" * 14  # 20 bytes
    assert SseParser(max_line_bytes=20).feed(at_limit + b"\n\n") == [RawEvent("message", "a" * 14)]
    with pytest.raises(SseProtocolError):
        SseParser(max_line_bytes=20).feed(at_limit + b"a\n\n")


def test_a_line_that_never_ends_is_refused_instead_of_growing_forever() -> None:
    parser = SseParser(max_line_bytes=20)
    parser.feed(b"data: " + b"a" * 14)  # 20 bytes sin salto de línea: aún cabe
    with pytest.raises(SseProtocolError):
        parser.feed(b"a")


def test_a_carriage_return_waiting_for_its_line_feed_still_counts_for_the_limit() -> None:
    with pytest.raises(SseProtocolError):
        SseParser(max_line_bytes=20).feed(b"data: " + b"a" * 15 + b"\r")


def test_an_event_exactly_at_the_limit_is_fine_and_one_byte_more_is_not() -> None:
    first, second = b"data: " + b"a" * 9, b"data: " + b"b" * 9  # 15 + 15 = 30 bytes de campos
    assert SseParser(max_event_bytes=30).feed(first + b"\n" + second + b"\n\n") == [
        RawEvent("message", "a" * 9 + "\n" + "b" * 9)
    ]
    with pytest.raises(SseProtocolError):
        SseParser(max_event_bytes=30).feed(first + b"\n" + second + b"b\n\n")


def test_the_event_limit_restarts_with_each_event() -> None:
    line = b"data: " + b"a" * 9 + b"\n"  # 15 bytes
    assert len(SseParser(max_event_bytes=30).feed((line + b"\n") * 5)) == 5
    assert len(SseParser(max_event_bytes=30).feed((line * 2 + b"\n") * 3)) == 3


def test_a_default_limit_is_wide_enough_for_every_contract_example() -> None:
    for name in CHAT_NAMES:
        SseParser().feed(chat_bytes(name))


@pytest.mark.parametrize("bad", [b"data: \xff\n\n", b"data: \xc3\n\n", b"event: \xe2\x82\ndata: 1\n\n"])
def test_invalid_utf8_is_refused(bad: bytes) -> None:
    with pytest.raises(SseProtocolError):
        SseParser().feed(bad)


def test_protocol_errors_carry_nothing_from_the_stream() -> None:
    secret = b"SECRETO-DEL-AGENTE"
    with pytest.raises(SseProtocolError) as caught:
        SseParser(max_line_bytes=10).feed(b"data: " + secret + b"\n\n")
    assert b"SECRETO" not in str(caught.value).encode() and caught.value.__context__ is None
    with pytest.raises(SseProtocolError) as caught:
        SseParser().feed(b"data: " + secret + b"\xff\n\n")
    assert b"SECRETO" not in str(caught.value).encode() and caught.value.__suppress_context__


# --- De evento a frame del contrato -------------------------------------------------------------------------------------------------------------


def test_the_known_events_are_exactly_the_seven_of_the_contract() -> None:
    assert {"token", "citation", "tool_call", "abstention", "usage", "done", "error"} == KNOWN_EVENTS


@pytest.mark.parametrize("event", ["message", "ping", "TOKEN", "Token ", "", "tokens", "heartbeat", "status"])
def test_an_unknown_event_is_dropped_whatever_its_data(event: str) -> None:
    assert decode_frame(event, '{"delta":"x"}') is None
    assert decode_frame(event, "esto no es JSON") is None


@pytest.mark.parametrize("name", CHAT_NAMES)
def test_every_event_of_every_example_decodes_to_the_frame_the_contract_tools_see(name: str) -> None:
    spec = importlib.util.spec_from_file_location(
        "validate_examples", REPO / "contracts" / "tools" / "validate_examples.py"
    )
    assert spec is not None and spec.loader is not None
    tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools)
    expected = tools.parse_sse(chat_bytes(name).decode("utf-8"))
    frames = frames_of(chat_bytes(name))
    assert [f.root.event for f in frames] == [e["event"] for e in expected]
    for frame, raw in zip(frames, expected, strict=True):
        assert frame.root.data.model_dump(mode="json") == raw["data"]


def test_only_done_and_error_end_a_stream() -> None:
    assert [is_terminal(f) for f in frames_of(chat_bytes("answer_with_tool"))] == [False] * 5 + [True]
    assert is_terminal(frames_of(chat_bytes("error_upstream"))[-1])
    assert is_terminal(frames_of(chat_bytes("error_tool"))[-1])


@pytest.mark.parametrize(
    ("event", "data"),
    [
        ("token", "no es json"),
        ("token", ""),
        ("token", "[]"),
        ("token", "null"),
        ("token", "{}"),
        ("token", '{"delta": 5}'),
        ("token", '{"delta": ["x"]}'),
        ("citation", '{"id": "1"}'),
        (
            "citation",
            '{"id":"1","title":"t","publisher":"p","url":"no-es-una-url","valid_as_of":"2026-09-01","quote":null}',
        ),
        (
            "citation",
            '{"id":"1","title":"t","publisher":"p","url":"https://x.example/a","valid_as_of":"01/09/2026","quote":null}',
        ),
        ("tool_call", '{"name":"buscar_facturas","status":"unknown"}'),
        ("abstention", '{"reason":"because","referral":null}'),
        ("abstention", '{"reason":"no_source","referral":"fiscalista"}'),
        ("usage", '{"input_tokens": "5", "output_tokens": 1, "cost_eur": null}'),
        ("usage", '{"input_tokens": 5, "output_tokens": 1, "cost_eur": 0.5}'),
        ("done", '{"finish_reason":"stop"}'),
        ("done", '{"finish_reason":"cut","trace_id":"t"}'),
        ("error", '{"code":"boom","message":"x"}'),
        ("token", '{"delta": NaN}'),
        ("token", '{"delta": Infinity}'),
        ("token", "[" * 100_000),
    ],
)
def test_a_known_event_with_data_that_breaks_the_contract_is_refused(event: str, data: str) -> None:
    with pytest.raises(InvalidFrame):
        decode_frame(event, data)


def test_extra_fields_are_ignored_as_the_contract_says() -> None:
    frame = decode_frame("token", '{"delta":"hola","campo_nuevo":1}')
    assert frame is not None and frame.root.data.model_dump() == {"delta": "hola"}


def test_a_frame_that_tries_to_smuggle_a_different_event_through_its_data_is_not_a_different_event() -> None:
    """El `data` se parsea antes de montar el sobre: no hay forma de inyectar claves en `{event, data}` con texto."""
    with pytest.raises(InvalidFrame):
        decode_frame("token", '{"delta":"x"}, "event":"done"')
    frame = decode_frame("token", '{"delta":"x","event":"done"}')
    assert frame is not None and frame.root.event == "token"


def test_the_error_of_an_invalid_frame_does_not_carry_the_data() -> None:
    with pytest.raises(InvalidFrame) as caught:
        decode_frame("token", '{"delta": 5, "secreto": "SECRETO-DEL-AGENTE"}')
    assert "SECRETO" not in str(caught.value) and caught.value.__suppress_context__ and caught.value.__cause__ is None


# --- Un flujo ya leído entero ---------------------------------------------------------------------------------------------------------------


def test_frames_of_drops_unknown_events_and_keeps_the_rest_in_order() -> None:
    payload = b'event: token\ndata: {"delta":"a"}\n\nevent: ping\ndata: 1\n\nevent: token\ndata: {"delta":"b"}\n\n'
    assert [f.root.data.delta for f in frames_of(payload)] == ["a", "b"]  # type: ignore[union-attr]


def test_frames_of_refuses_a_stream_that_ends_in_the_middle_of_an_event() -> None:
    with pytest.raises(SseProtocolError):
        frames_of(b'event: token\ndata: {"delta":"a"}\n')
    with pytest.raises(SseProtocolError):
        frames_of(b'event: token\ndata: {"delta":"a"}\n\nevent: do')


def test_the_raw_events_of_the_examples_are_json_objects() -> None:
    for name in CHAT_NAMES:
        for event in whole(name):
            assert isinstance(json.loads(event.data), dict), (name, event.name)
