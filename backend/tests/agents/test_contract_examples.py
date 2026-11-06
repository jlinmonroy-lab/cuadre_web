"""AC-08 · El cliente cumple el contrato C1 con los ejemplos de `contracts/examples/extract/`."""

import json

import pytest
from jsonschema import Draft202012Validator

from cuadre.agents import FakeAgentsClient, HttpAgentsClient, normalize_extraction
from cuadre.agents.fake import DEFAULT_SEQUENCE
from cuadre_contracts import ExtractRequest, ExtractResponse
from cuadre_contracts.extract import AgentError
from tests.agents.server import Reply, ScriptedServer
from tests.agents.support import (
    API_KEY,
    EXAMPLES,
    RESPONSE_NAMES,
    SCHEMAS,
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
