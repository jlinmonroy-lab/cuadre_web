"""Fixtures de la API del chat: la aplicación REAL con base de datos real y el agente simulado (o uno de `fakes.py`).

Los tokens son los de la clave de prueba de `tests/api/conftest.py` (la API los verifica con su JWKS). `raise_server_exceptions=False`: un error
inesperado se ve como lo vería un cliente real (un 500).
"""

import json
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import FakeAgentsClient
from cuadre.agents.fake import ChatScriptItem
from cuadre.core.auth import JwksTokenVerifier
from cuadre.main import create_app
from tests.agents.conftest import server  # noqa: F401 - fixture de otro conftest
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.clocks import FixedClock
from tests.support import Cast, Person

TODAY = "2026-11-16"
QUESTION = "¿Qué mención lleva una factura a una empresa alemana?"


@dataclass(frozen=True)
class Event:
    name: str
    data: dict[str, Any]


@dataclass
class Sent:
    """Lo que devolvió `POST /api/chat`: el estado, las cabeceras y los eventos (si fue un flujo) o el problema (si no)."""

    status: int
    headers: dict[str, str]
    raw: str
    events: list[Event] = field(default_factory=list)
    problem: dict[str, Any] | None = None

    @property
    def names(self) -> list[str]:
        return [e.name for e in self.events]

    def of(self, name: str) -> list[Event]:
        return [e for e in self.events if e.name == name]

    @property
    def text(self) -> str:
        return "".join(e.data["delta"] for e in self.of("token"))

    @property
    def terminal(self) -> Event:
        assert self.events and self.events[-1].name in ("done", "error"), self.names
        return self.events[-1]

    @property
    def conversation_id(self) -> UUID:
        return UUID(self.of("start")[0].data["conversation_id"])

    @property
    def message_id(self) -> UUID:
        return UUID(self.of("start")[0].data["message_id"])


def parse_events(raw: str) -> list[Event]:
    events: list[Event] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        name = ""
        data = ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        events.append(Event(name, json.loads(data)))
    return events


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer
    cast: Cast

    def token(self, person: Person) -> str:
        return self.signer.token(person)

    def headers(self, person: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(person)}"}

    def request(self, method: str, url: str, person: Person, **kwargs: Any) -> httpx.Response:
        return self.client.request(method, url, headers=self.headers(person), **kwargs)

    # --- El agente ---------------------------------------------------------------------------------------------------------

    def script(self, *items: ChatScriptItem) -> FakeAgentsClient:
        """El agente simulado responderá exactamente esto, en orden (y fallará si se le pide más)."""
        fake = FakeAgentsClient(chat_script=items)
        self.app.state.agents_client = fake
        return fake

    def use(self, agent: Any) -> Any:
        self.app.state.agents_client = agent
        return agent

    @property
    def agent(self) -> Any:
        return self.app.state.agents_client

    # --- Enviar y leer -----------------------------------------------------------------------------------------------------

    def send(self, person: Person, content: str = QUESTION, conversation_id: UUID | str | None = None) -> Sent:
        body = {"conversation_id": None if conversation_id is None else str(conversation_id), "content": content}
        with self.client.stream("POST", "/api/chat", headers=self.headers(person), json=body) as response:
            raw = response.read().decode("utf-8")
            status, headers = response.status_code, dict(response.headers)
        if status == 200:
            return Sent(status, headers, raw, events=parse_events(raw))
        return Sent(status, headers, raw, problem=json.loads(raw))

    def conversations(self, person: Person) -> list[dict[str, Any]]:
        response = self.request("GET", "/api/chat/conversations", person)
        assert response.status_code == 200, response.text
        items: list[dict[str, Any]] = response.json()["items"]
        return items

    def conversation(self, person: Person, conversation_id: UUID | str) -> httpx.Response:
        return self.request("GET", f"/api/chat/conversations/{conversation_id}", person)

    def rate(self, person: Person, message_id: UUID | str, rating: str, reason: str | None = None) -> httpx.Response:
        return self.request(
            "PUT", f"/api/chat/messages/{message_id}/feedback", person, json={"rating": rating, "reason": reason}
        )


@pytest.fixture
def app(jwks_client: FakeJwksClient) -> FastAPI:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.state.clock = FixedClock(datetime(2026, 11, 16, 10, 0, tzinfo=ZoneInfo("Europe/Madrid")))
    return application


@pytest.fixture
def api(app: FastAPI, signer: Signer, cast: Cast) -> Iterator[Api]:  # noqa: F811
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(app, client, signer, cast)


# --- Estado de la base de datos (solo para comprobar) --------------------------------------------------------------------------


def stored(admin: Connection[DictRow], conversation_id: UUID | str) -> list[dict[str, Any]]:
    return admin.execute(
        "select id, role, content, status, finish_reason, trace_id, has_source, citations, abstention, created_at "
        "from public.chat_messages where conversation_id = %s order by created_at, id",
        (conversation_id,),
    ).fetchall()


def conversation_count(admin: Connection[DictRow], owner: Person) -> int:
    row = admin.execute(
        "select count(*) as n from public.chat_conversations where owner_id = %s", (owner.id,)
    ).fetchone()
    assert row is not None
    return int(row["n"])


def random_uuid() -> str:
    return str(uuid.uuid4())
