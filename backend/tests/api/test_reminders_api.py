"""AC-13 · Los ajustes de recordatorios por la API (SPEC-W-014 §5.3, D-01), con la aplicación REAL y la base de datos real."""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.auth import JwksTokenVerifier
from cuadre.jobs.reminders import due_quarter
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.support import Cast, Person

URL = "/api/me/reminders"
DEFAULTS = {"enabled": True, "lead_days": 10}


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer

    def request(self, method: str, person: Person | None, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.signer.token(person)}"} if person is not None else {}
        return self.client.request(method, URL, headers=headers, **kwargs)

    def get(self, person: Person | None) -> httpx.Response:
        return self.request("GET", person)

    def put(self, person: Person | None, body: object) -> httpx.Response:
        return self.request("PUT", person, json=body)


@pytest.fixture
def api(jwks_client: FakeJwksClient, signer: Signer) -> Iterator[Api]:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    with TestClient(application, raise_server_exceptions=False) as client:
        yield Api(application, client, signer)


def test_without_saved_settings_the_defaults_apply(api: Api, cast: Cast) -> None:
    response = api.get(cast.alicia)
    assert response.status_code == 200 and response.json() == DEFAULTS
    assert response.headers["cache-control"] == "private, no-store"


def test_saving_then_reading_returns_what_was_saved_and_the_job_uses_it(
    api: Api, admin: Connection[DictRow], cast: Cast
) -> None:
    response = api.put(cast.alicia, {"enabled": False, "lead_days": 14})
    assert response.status_code == 200 and response.json() == {"enabled": False, "lead_days": 14}
    assert api.get(cast.alicia).json() == {"enabled": False, "lead_days": 14}
    row = admin.execute(
        "select enabled, lead_days from public.reminder_settings where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert row == {"enabled": False, "lead_days": 14}
    # El job lee los mismos ajustes: con 14 días el aviso del 4T sale el 16 de enero y no el 15.
    assert due_quarter(date(2027, 1, 16), row["lead_days"]) is not None
    assert due_quarter(date(2027, 1, 15), row["lead_days"]) is None


def test_saving_twice_updates_the_same_row(api: Api, admin: Connection[DictRow], cast: Cast) -> None:
    assert api.put(cast.alicia, {"enabled": True, "lead_days": 5}).status_code == 200
    assert api.put(cast.alicia, {"enabled": True, "lead_days": 30}).json() == {"enabled": True, "lead_days": 30}
    count = admin.execute("select count(*) as n from public.reminder_settings where owner_id = %s", (cast.alicia.id,))
    assert count.fetchone() == {"n": 1}


@pytest.mark.parametrize("days", [1, 10, 30])
def test_the_limits_are_accepted(api: Api, cast: Cast, days: int) -> None:
    assert api.put(cast.alicia, {"enabled": True, "lead_days": days}).json()["lead_days"] == days


@pytest.mark.parametrize("days", [0, 31, -1, 1000])
def test_a_lead_outside_one_to_thirty_is_refused_and_nothing_changes(
    api: Api, admin: Connection[DictRow], cast: Cast, days: int
) -> None:
    response = api.put(cast.alicia, {"enabled": True, "lead_days": days})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_lead_days" and body["field"] == "lead_days"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert (
        body["detail"] == "La antelación debe ser un número entero de días entre 1 y 30."
    )  # fijo: no repite lo enviado
    assert api.get(cast.alicia).json() == DEFAULTS
    row = admin.execute("select 1 from public.reminder_settings where owner_id = %s", (cast.alicia.id,)).fetchone()
    assert row is None


@pytest.mark.parametrize(
    "body",
    [
        {"enabled": True, "lead_days": "7"},
        {"enabled": True, "lead_days": 7.5},
        {"enabled": True, "lead_days": True},
        {"enabled": "yes", "lead_days": 7},
        {"enabled": 1, "lead_days": 7},
        {"enabled": None, "lead_days": 7},
        {"enabled": True, "lead_days": None},
        {"enabled": True},
        {"lead_days": 7},
        {},
        {"enabled": True, "lead_days": 7, "owner_id": "x"},
        [],
        "7",
    ],
)
def test_a_body_of_the_wrong_shape_is_a_validation_error(api: Api, cast: Cast, body: object) -> None:
    response = api.put(cast.alicia, body)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert api.get(cast.alicia).json() == DEFAULTS


def test_without_a_session_the_answer_is_401(api: Api) -> None:
    assert api.get(None).status_code == 401
    assert api.put(None, DEFAULTS).status_code == 401


@pytest.mark.parametrize("who", ["gina", "adan"])
def test_gestores_and_admins_cannot_use_it(api: Api, admin: Connection[DictRow], cast: Cast, who: str) -> None:
    person = cast[who]
    assert api.get(person).status_code == 403
    assert api.put(person, DEFAULTS).status_code == 403
    assert admin.execute("select 1 from public.reminder_settings where owner_id = %s", (person.id,)).fetchone() is None


def test_a_suspended_account_cannot_use_it(api: Api, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert api.get(cast.alicia).status_code == 403
    assert api.put(cast.alicia, DEFAULTS).status_code == 403


def test_one_user_never_sees_or_changes_the_settings_of_another(api: Api, cast: Cast) -> None:
    assert api.put(cast.alicia, {"enabled": False, "lead_days": 3}).status_code == 200
    assert api.get(cast.beto).json() == DEFAULTS
    assert api.put(cast.beto, {"enabled": True, "lead_days": 20}).status_code == 200
    assert api.get(cast.alicia).json() == {"enabled": False, "lead_days": 3}


def test_both_routes_are_in_the_public_contract(api: Api) -> None:
    paths = api.app.openapi()["paths"]["/api/me/reminders"]
    assert paths["get"]["operationId"] == "get_reminder_settings"
    assert paths["put"]["operationId"] == "update_reminder_settings"
