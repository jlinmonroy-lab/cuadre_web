"""Forma de los errores, identificador de petición, CORS y orden commit-antes-de-responder (SPEC-W-001 §5.1, T-10)."""

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import cuadre.core.auth as auth_module
from cuadre import __version__
from cuadre.config import Settings
from cuadre.core.auth import JwksTokenVerifier, Tx
from cuadre.main import create_app
from tests.api.conftest import FakeJwksClient, Signer, bearer
from tests.support import Cast

ORIGIN = "http://localhost:3000"


@pytest.fixture
def probes(app: FastAPI) -> FastAPI:
    def echo(n: int) -> dict[str, int]:
        return {"n": n}

    def boom() -> None:
        raise RuntimeError("secreto-interno-xyz")

    def busy() -> None:
        raise PoolTimeout("agotado")

    app.add_api_route("/_t/echo", echo, methods=["GET"], operation_id="get_probe_echo")
    app.add_api_route("/_t/boom", boom, methods=["GET"], operation_id="get_probe_boom")
    app.add_api_route("/_t/busy", busy, methods=["GET"], operation_id="get_probe_busy")
    return app


def test_health_needs_no_authentication(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_unknown_route_is_a_problem_404(client: TestClient) -> None:
    response = client.get("/no-existe")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert (body["code"], body["status"], body["type"]) == ("not_found", 404, "about:blank")
    assert body["request_id"] == response.headers["x-request-id"]


def test_wrong_method_is_a_problem_405_with_allow(client: TestClient) -> None:
    response = client.post("/healthz")
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert "GET" in response.headers["allow"]


@pytest.mark.usefixtures("probes")
def test_validation_errors_report_the_location_but_never_echo_the_input(client: TestClient) -> None:
    response = client.get("/_t/echo?n=dato-privado-abc")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert [e["loc"] for e in body["errors"]] == ["query.n"]
    assert "dato-privado-abc" not in response.text
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.usefixtures("probes")
def test_an_unexpected_error_is_a_500_without_internals_and_keeps_cors(client: TestClient) -> None:
    response = client.get("/_t/boom", headers={"Origin": ORIGIN})
    assert response.status_code == 500
    body = response.json()
    assert (body["code"], body["status"]) == ("internal_error", 500)
    assert "secreto-interno-xyz" not in response.text
    assert "Traceback" not in response.text and "RuntimeError" not in response.text
    assert body["request_id"] == response.headers["x-request-id"]
    assert response.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.usefixtures("probes")
def test_pool_exhaustion_is_a_fast_503_not_a_hang(client: TestClient) -> None:
    response = client.get("/_t/busy")
    assert response.status_code == 503
    assert response.json()["code"] == "database_busy"
    assert response.headers["retry-after"]


def test_a_well_formed_request_id_is_kept_and_a_bad_one_is_replaced(client: TestClient) -> None:
    assert client.get("/healthz", headers={"X-Request-Id": "abc-12345-DEF"}).headers["x-request-id"] == "abc-12345-DEF"
    for junk in ("corto", "con espacios y demasiado raro!", "x" * 200, "<script>alert(1)</script>"):
        returned = client.get("/healthz", headers={"X-Request-Id": junk}).headers["x-request-id"]
        assert returned != junk
        assert re.fullmatch(r"[0-9a-f]{32}", returned)


# --- CORS -------------------------------------------------------------------------------------------------------------------


def test_cors_allows_only_the_frontend_origin(client: TestClient) -> None:
    allowed = client.options(
        "/api/me",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-credentials" not in allowed.headers, "la API usa Bearer, no cookies"

    denied = client.options(
        "/api/me", headers={"Origin": "https://evil.example.test", "Access-Control-Request-Method": "GET"}
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers

    simple = client.get("/healthz", headers={"Origin": "https://evil.example.test"})
    assert "access-control-allow-origin" not in simple.headers


def test_the_request_id_is_readable_from_the_browser(client: TestClient) -> None:
    response = client.get("/healthz", headers={"Origin": ORIGIN})
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


# --- Configuración ----------------------------------------------------------------------------------------------------------


def test_the_interactive_docs_are_off_in_production() -> None:
    # En producción la API exige el servicio de agentes (SPEC-W-002 D-06): sin AGENTS_BASE_URL no arrancaría.
    production = create_app(
        Settings(app_env="production", agents_base_url="https://agents.example.test", agents_api_key="clave-de-prueba")  # type: ignore[call-arg]
    )
    development = create_app(Settings(app_env="local"))  # type: ignore[call-arg]
    with TestClient(production) as prod, TestClient(development) as dev:
        assert prod.get("/docs").status_code == 404
        assert dev.get("/docs").status_code == 200


# --- Commit antes de responder ----------------------------------------------------------------------------------------------


def test_the_transaction_is_committed_before_the_response_is_sent(
    signer: Signer, jwks_client: FakeJwksClient, cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Depends(get_tx, scope="function")`: si el commit fallara, el cliente lo sabría (500) en vez de ver un 200 falso."""
    events: list[str] = []
    real = auth_module.user_transaction

    @contextmanager
    def spy(*args: object, **kwargs: object) -> Iterator[object]:
        with real(*args, **kwargs) as conn:  # type: ignore[arg-type]
            yield conn
        events.append("transaction_closed")

    class Recorder:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            async def watch(message: Message) -> None:
                if message["type"] == "http.response.start":
                    events.append("response_started")
                await send(message)

            await self.app(scope, receive, watch)

    monkeypatch.setattr(auth_module, "user_transaction", spy)

    def probe(conn: Tx) -> dict[str, int]:
        events.append("route_ran")
        return {"one": conn.execute("select 1 as one").fetchone()["one"]}  # type: ignore[index]

    application = create_app(Settings())  # type: ignore[call-arg]
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.add_api_route("/_t/probe", probe, methods=["GET"], operation_id="get_probe_tx")
    application.add_middleware(Recorder)
    with TestClient(application) as test_client:
        assert test_client.get("/_t/probe", headers=bearer(signer.token(cast.alicia))).status_code == 200

    assert events == ["route_ran", "transaction_closed", "response_started"]
