"""AC-15 · La ruta interna del planificador ejecuta el cierre mensual (SPEC-W-012 §5.3, ADR-0016).

La ruta no admite `only_owners`, y la base de pruebas acumula miles de cuentas de otras pruebas: aquí se registra un envoltorio que limita el job a las cuentas
de la prueba. Las reglas de acceso (401, secreto ausente, 404, 503) son las mismas que ya prueba `test_recordatorios_internal_route.py`.
"""

import dataclasses
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cuadre.jobs import runner
from cuadre.jobs.closing_job import run_monthly_closing
from tests.clocks import FixedClock
from tests.jobs.test_recordatorios_internal_route import SECRET, bearer, build
from tests.support import Cast

URL = "/internal/jobs/monthly_closing"
NOW = datetime(2026, 12, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def only(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    owners: list[UUID] = []

    def limited(context: runner.JobContext) -> dict[str, int]:
        scoped = dataclasses.replace(context, only_owners=owners)
        return run_monthly_closing(
            service_pool=scoped.service_pool,
            app_pool=scoped.app_pool,
            now=scoped.now,
            only_owners=scoped.only_owners,
            month=scoped.month,
        ).as_dict()

    monkeypatch.setitem(runner.JOBS, "monthly_closing", limited)
    return owners


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = build(cron_secret=SECRET)
    application.state.clock = FixedClock(NOW)
    with TestClient(application, raise_server_exceptions=False) as c:
        yield c


def test_with_the_secret_the_job_runs_and_returns_its_four_counters(
    client: TestClient, only: list[UUID], cast: Cast
) -> None:
    only.append(cast.alicia.id)
    first = client.get(URL, headers=bearer(SECRET))
    assert first.status_code == 200
    assert first.json() == {
        "closed": 1,
        "reopened": 0,
        "unchanged": 0,
        "failed": 0,
    }  # la cuenta nueva cierra su mes de alta
    again = client.get(URL, headers=bearer(SECRET))
    assert again.json() == {"closed": 0, "reopened": 0, "unchanged": 1, "failed": 0}  # repetir es seguro


@pytest.mark.parametrize("headers", [{}, bearer("otro"), bearer("")])
def test_without_the_right_secret_nothing_runs(
    client: TestClient, only: list[UUID], cast: Cast, headers: dict[str, str]
) -> None:
    only.append(cast.alicia.id)
    assert client.get(URL, headers=headers).status_code == 401


def test_the_route_is_not_in_the_public_contract(client: TestClient) -> None:
    schema = client.app.openapi()  # type: ignore[attr-defined]
    assert not any(path.startswith("/internal") for path in schema["paths"])
    assert "monthly_closing" not in str(schema)
