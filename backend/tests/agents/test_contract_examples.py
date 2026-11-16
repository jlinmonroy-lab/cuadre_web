"""AC-08 · El cliente cumple el contrato C1 con los ejemplos de `contracts/examples/extract/`."""

import json

import pytest
from jsonschema import Draft202012Validator

from cuadre.agents import FakeAgentsClient, HttpAgentsClient, normalize_extraction
from cuadre.agents.fake import CHAT_ERROR_FIXTURES, DEFAULT_CHAT_SEQUENCE, DEFAULT_SEQUENCE
from cuadre.agents.sse import frames_of
from cuadre_contracts import ExtractRequest, ExtractResponse
from cuadre_contracts.extract import AgentError
from tests.agents.server import Reply, ScriptedServer
from tests.agents.support import (
    API_KEY,
    CHAT_EXAMPLES,
    EXAMPLES,
    RESPONSE_NAMES,
    SCHEMAS,
    chat_bytes,
    chat_request,
    example_json,
    example_request,
    response_json,
)


def schema_validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


def test_there_are_six_examples_and_the_fake_knows_exactly_those() -> None:
    """Un fixture nuevo en la carpeta sin cablear en el Fake (o al revés) hace fallar esto: hay que decidir dónde entra."""
    on_disk = {p.name.split(".")[0] for p in EXAMPLES.glob("*.response.json")} | {
        p.name.split(".")[0] for p in EXAMPLES.glob("*.error.json")
    }
    assert on_disk == set(DEFAULT_SEQUENCE)
    assert len(on_disk) == 6


@pytest.mark.parametrize("name", RESPONSE_NAMES)
def test_each_response_example_validates_and_normalizes(name: str) -> None:
    response = ExtractResponse.model_validate_json((EXAMPLES / f"{name}.response.json").read_bytes(), strict=True)
    schema_validator("extract_response.schema.json").validate(response_json(name))
    reading = normalize_extraction(response)
    assert reading.trace_id == response.trace_id


def test_the_error_example_validates() -> None:
    AgentError.model_validate_json((EXAMPLES / "unreadable.error.json").read_bytes(), strict=True)
    schema_validator("agent_error.schema.json").validate(example_json("unreadable.error.json"))


def test_the_request_example_validates() -> None:
    body = example_json("extract.request.json")
    ExtractRequest.model_validate(body)
    schema_validator("extract_request.schema.json").validate(body)


@pytest.mark.parametrize("name", RESPONSE_NAMES)
def test_the_http_client_accepts_each_response_example_as_the_fake_serves_it(server: ScriptedServer, name: str) -> None:
    server.serve(Reply(200, response_json(name)))
    over_http = HttpAgentsClient(server.url, API_KEY).extract_invoice(example_request(), request_id="req-0000001")
    from_fake = FakeAgentsClient([name]).extract_invoice(example_request(), request_id="req-0000001")
    assert over_http == from_fake
    assert normalize_extraction(over_http) == normalize_extraction(from_fake)


# --- C2 · Chat (SPEC-W-004, AC-23) ------------------------------------------------------------------------------------------------------


def test_there_are_eight_chat_streams_and_the_fake_knows_exactly_those() -> None:
    """Un `.sse` nuevo en la carpeta sin cablear en el Fake (o al revés) hace fallar esto: hay que decidir si entra en el ciclo o solo por marcador."""
    on_disk = {p.stem for p in CHAT_EXAMPLES.glob("*.sse")}
    assert on_disk == set(DEFAULT_CHAT_SEQUENCE) | set(CHAT_ERROR_FIXTURES)
    assert len(on_disk) == 8
    assert {p.name for p in CHAT_EXAMPLES.iterdir()} == {f"{n}.sse" for n in on_disk} | {
        "chat.request.json",
        "chat_no_tools.request.json",
    }


@pytest.mark.parametrize("name", ["chat", "chat_no_tools"])
def test_each_chat_request_example_validates_and_round_trips(name: str) -> None:
    raw = json.loads((CHAT_EXAMPLES / f"{name}.request.json").read_text(encoding="utf-8"))
    schema_validator("chat_request.schema.json").validate(raw)
    request = chat_request(name)
    assert (
        json.loads(request.model_dump_json()) == raw
    )  # lo que enviamos es exactamente el ejemplo, `mcp_url: null` incluido


def test_the_two_request_examples_cover_with_and_without_tools() -> None:
    assert chat_request("chat").mcp_url is not None
    without = chat_request("chat_no_tools")
    assert without.mcp_url is None and len(without.messages) == 3 and without.messages[-1].role == "user"
    assert [m.role for m in without.messages] == ["user", "assistant", "user"]


def test_the_no_source_and_out_of_scope_abstentions_cover_the_referrals() -> None:
    referrals = {}
    for name in ("abstention_professional", "abstention_no_source", "abstention_out_of_scope"):
        frame = next(f for f in frames_of(chat_bytes(name)) if f.root.event == "abstention")
        referrals[name] = (frame.root.data.reason.value, frame.root.data.referral)  # type: ignore[union-attr]
    assert referrals == {
        "abstention_professional": ("professional_judgment", "gestor"),
        "abstention_no_source": ("no_source", "asesor"),
        "abstention_out_of_scope": ("out_of_scope", None),
    }


def test_the_examples_cover_every_finish_reason_and_every_error_code_the_web_handles() -> None:
    reasons, codes = set(), set()
    for name in sorted(p.stem for p in CHAT_EXAMPLES.glob("*.sse")):
        for frame in frames_of(chat_bytes(name)):
            if frame.root.event == "done":
                reasons.add(frame.root.data.finish_reason.value)  # type: ignore[union-attr]
            if frame.root.event == "error":
                codes.add(frame.root.data.code.value)  # type: ignore[union-attr]
    assert reasons == {"stop", "abstained", "length"}
    assert codes == {"upstream_error", "tool_error"}
