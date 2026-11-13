"""AC-14 · La ruta interna del planificador (SPEC-W-014 §5.3, D-06, ADR-0016)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuadre.main import create_app
from cuadre.notifications import MemoryEmailSender
from tests.agents.support import make_settings
from tests.clocks import FixedClock

SECRET = "secreto-de-prueba-del-planificador"
URL = "/internal/jobs/reminders"


def build(**settings: object) -> FastAPI:
    application = create_app(
        make_settings(
            database_url=os.environ["DATABASE_URL"],
            database_service_url=os.environ["DATABASE_SERVICE_URL"],
            supabase_url=os.environ["SUPABASE_URL"],
            **settings,
        )
    )
    application.state.email_sender = MemoryEmailSender()
    application.state.clock = FixedClock(datetime(2026, 5, 15, 8, 0, tzinfo=UTC))  # entre plazos: nadie recibe nada
    return application


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(build(cron_secret=SECRET), raise_server_exceptions=False) as c:
        yield c


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


@pytest.mark.parametrize(
    "headers", [{}, bearer("otro"), bearer(""), {"Authorization": SECRET}, {"Authorization": "Basic x"}]
)
def test_without_the_right_secret_the_answer_is_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(URL, headers=headers)
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert SECRET not in response.text


def test_without_a_configured_secret_the_route_is_never_open() -> None:
    with TestClient(build(), raise_server_exceptions=False) as c:
        assert c.get(URL).status_code == 401
        assert c.get(URL, headers=bearer("")).status_code == 401
        assert c.get(URL, headers=bearer("None")).status_code == 401


def test_with_the_secret_the_job_runs_and_returns_its_counters(client: TestClient) -> None:
    response = client.get(URL, headers=bearer(SECRET))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"sent", "skipped", "failed"}
    assert body["sent"] == 0 and body["failed"] == 0  # el 15 de mayo no hay ningún plazo en la ventana


def test_an_unknown_job_is_404(client: TestClient) -> None:
    response = client.get("/internal/jobs/nada", headers=bearer(SECRET))
    assert response.status_code == 404 and response.json()["code"] == "job_not_found"


def test_without_the_service_database_the_job_is_unavailable() -> None:
    application = build(cron_secret=SECRET)
    application.state.settings = application.state.settings.model_copy(update={"database_service_url": None})
    with TestClient(application, raise_server_exceptions=False) as c:
        response = c.get(URL, headers=bearer(SECRET))
    assert response.status_code == 503 and response.json()["code"] == "job_unavailable"


def test_the_route_is_not_in_the_public_contract(client: TestClient) -> None:
    schema = client.app.openapi()  # type: ignore[attr-defined]
    assert not any(path.startswith("/internal") for path in schema["paths"])
    assert "run_job" not in str(schema)
