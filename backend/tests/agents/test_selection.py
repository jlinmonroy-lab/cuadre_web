"""AC-08 · Qué cliente de agentes se usa según el entorno (SPEC-W-002 D-06, ADR-0012)."""

from typing import Any

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from cuadre.agents import (
    AgentsConfigurationError,
    FakeAgentsClient,
    HttpAgentsClient,
    get_agents_client,
)
from cuadre.config import Settings
from cuadre.main import create_app
from tests.agents.server import Reply, ScriptedServer
from tests.agents.support import API_KEY, captured_logs, example_request, make_settings, response_json
from tests.rules.paths import REPO

URL = "https://agents.example.test"


def endpoint(c: Any) -> str:
    assert isinstance(c, HttpAgentsClient)
    return c._endpoint  # lo único que no se ve desde fuera sin abrir una conexión


# --- La matriz de D-06 -----------------------------------------------------------------------------------------------------------


def test_without_a_url_local_uses_the_fake() -> None:
    assert isinstance(get_agents_client(make_settings(app_env="local")), FakeAgentsClient)


def test_without_a_url_staging_uses_the_fake_and_says_so() -> None:
    with captured_logs("cuadre.agents") as records:
        client = get_agents_client(make_settings(app_env="staging"))
    assert isinstance(client, FakeAgentsClient)
    assert [(r.levelname, r.getMessage()) for r in records] == [("WARNING", "agents_fake_in_use")]


def test_without_a_url_production_refuses_to_start() -> None:
    with pytest.raises(AgentsConfigurationError, match="AGENTS_BASE_URL"):
        get_agents_client(make_settings(app_env="production"))


@pytest.mark.parametrize("env", ["local", "staging", "production"])
def test_with_a_url_and_a_key_the_http_client_is_used(env: str) -> None:
    client = get_agents_client(make_settings(app_env=env, agents_base_url=URL, agents_api_key=API_KEY))
    assert isinstance(client, HttpAgentsClient)
    assert endpoint(client) == f"{URL}/v1/extract"


@pytest.mark.parametrize("env", ["local", "staging", "production"])
def test_a_url_without_a_key_is_a_configuration_error_in_every_environment(env: str) -> None:
    with pytest.raises(AgentsConfigurationError, match="AGENTS_API_KEY"):
        get_agents_client(make_settings(app_env=env, agents_base_url=URL))


@pytest.mark.parametrize("env", ["staging", "production"])
def test_plain_http_is_only_accepted_in_local(env: str) -> None:
    with pytest.raises(AgentsConfigurationError, match="https"):
        get_agents_client(
            make_settings(app_env=env, agents_base_url="http://agents.example.test", agents_api_key=API_KEY)
        )
    local = get_agents_client(
        make_settings(app_env="local", agents_base_url="http://127.0.0.1:8001", agents_api_key=API_KEY)
    )
    assert endpoint(local) == "http://127.0.0.1:8001/v1/extract"


@pytest.mark.parametrize(
    "url",
    [
        "agents.example.test",  # sin esquema
        "ftp://agents.example.test",
        "https://",
        "https://user:secret@agents.example.test",
        "https://:secret@agents.example.test",
        "https://agents.example.test?token=abc",
        "https://agents.example.test/path?x=1",
        "https://agents.example.test#fragment",
        "https://agents.example.test:notaport",
        "https://agents.example.test:99999",
    ],
)
def test_a_malformed_or_risky_base_url_is_refused_without_echoing_it(url: str) -> None:
    with pytest.raises(AgentsConfigurationError) as caught:
        get_agents_client(make_settings(app_env="local", agents_base_url=url, agents_api_key=API_KEY))
    assert "secret" not in str(caught.value) and "token=abc" not in str(caught.value)
    assert url not in str(caught.value)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://agents.example.test", "https://agents.example.test/v1/extract"),
        ("https://agents.example.test/", "https://agents.example.test/v1/extract"),
        ("  https://agents.example.test  ", "https://agents.example.test/v1/extract"),
        ("https://agents.example.test:8443/", "https://agents.example.test:8443/v1/extract"),
        ("https://agents.example.test/api/", "https://agents.example.test/api/v1/extract"),
        ("https://[::1]:8443", "https://[::1]:8443/v1/extract"),
    ],
)
def test_the_base_url_is_normalized(given: str, expected: str) -> None:
    client = get_agents_client(make_settings(agents_base_url=given, agents_api_key=API_KEY))
    assert endpoint(client) == expected


# --- Lo que viene del entorno ---------------------------------------------------------------------------------------------------


def test_blank_values_mean_absent_so_the_env_template_selects_the_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    """`.env.example` trae `AGENTS_BASE_URL=` y `AGENTS_API_KEY=` vacíos: eso es «sin servicio», no una URL vacía."""
    template = dotenv_values(REPO / ".env.example")
    assert template["AGENTS_BASE_URL"] == "" and template["AGENTS_API_KEY"] == ""
    for name in ("AGENTS_BASE_URL", "AGENTS_API_KEY", "AGENTS_TIMEOUT_SECONDS"):
        monkeypatch.setenv(name, template[name] or "")
    settings = Settings(
        _env_file=None, supabase_url="http://127.0.0.1:54321", database_url="postgresql://x@127.0.0.1:5/x"
    )
    assert settings.agents_base_url is None and settings.agents_api_key is None
    assert settings.agents_timeout_seconds == 45
    assert isinstance(get_agents_client(settings), FakeAgentsClient)


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_url_and_key_are_none_even_when_given_explicitly(blank: str) -> None:
    settings = make_settings(agents_base_url=blank, agents_api_key=blank)
    assert settings.agents_base_url is None and settings.agents_api_key is None


def test_a_blank_key_with_a_url_is_a_missing_key() -> None:
    with pytest.raises(AgentsConfigurationError, match="AGENTS_API_KEY"):
        get_agents_client(make_settings(agents_base_url=URL, agents_api_key="  "))


def test_the_key_is_trimmed_and_never_shown() -> None:
    settings = make_settings(agents_base_url=URL, agents_api_key=f"  {API_KEY}\n")
    assert settings.agents_api_key is not None and settings.agents_api_key.get_secret_value() == API_KEY
    assert API_KEY not in repr(settings) and API_KEY not in str(settings.model_dump())


@pytest.mark.parametrize("seconds", [1, 45, 120])
def test_the_time_budget_is_taken_from_settings_in_milliseconds(seconds: int) -> None:
    client = get_agents_client(
        make_settings(agents_base_url=URL, agents_api_key=API_KEY, agents_timeout_seconds=seconds)
    )
    assert isinstance(client, HttpAgentsClient)
    assert client._timeout_ms == seconds * 1000


@pytest.mark.parametrize("seconds", [0, -1, 121, 3600])
def test_a_time_budget_outside_one_to_120_seconds_is_refused(seconds: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(agents_timeout_seconds=seconds)


def test_the_default_budget_is_the_45_seconds_of_the_spec() -> None:
    assert make_settings().agents_timeout_seconds == 45
    client = get_agents_client(make_settings(agents_base_url=URL, agents_api_key=API_KEY))
    assert isinstance(client, HttpAgentsClient) and client._timeout_ms == 45_000


def test_the_selected_http_client_really_talks_to_the_configured_url(server: ScriptedServer) -> None:
    server.serve(Reply(200, response_json("invoice_ok")))
    client = get_agents_client(make_settings(agents_base_url=server.url, agents_api_key=API_KEY))
    assert client.extract_invoice(example_request(), request_id="req-0000001").trace_id == "trc_synthetic_0001"
    assert server.seen[0].path == "/v1/extract"


# --- La API --------------------------------------------------------------------------------------------------------------------


def test_the_app_keeps_the_selected_client_in_its_state() -> None:
    app = create_app(make_settings())
    assert isinstance(app.state.agents_client, FakeAgentsClient)
    configured = create_app(make_settings(agents_base_url=URL, agents_api_key=API_KEY))
    assert isinstance(configured.state.agents_client, HttpAgentsClient)


def test_the_api_does_not_start_in_production_without_the_agents_service() -> None:
    with pytest.raises(AgentsConfigurationError):
        create_app(make_settings(app_env="production"))
    with pytest.raises(AgentsConfigurationError):
        create_app(make_settings(app_env="production", agents_base_url=URL))  # sin clave
    with pytest.raises(AgentsConfigurationError):
        create_app(
            make_settings(app_env="production", agents_base_url="http://agents.example.test", agents_api_key=API_KEY)
        )
    create_app(make_settings(app_env="production", agents_base_url=URL, agents_api_key=API_KEY))  # completa: arranca
