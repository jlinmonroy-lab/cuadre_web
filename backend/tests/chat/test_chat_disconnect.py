"""AC-13 · El navegador corta a mitad de la respuesta (SPEC-W-004 §7, D-07).

`TestClient` no simula un corte de verdad (su `receive` espera a que la respuesta termine), así que aquí se llama a la aplicación ASGI directamente con un
`receive` y un `send` a mano. Hay dos formas de que Starlette se entere, según lo que anuncie el servidor (`spec_version`):

* **2.3** (uvicorn actual): `receive` entrega `http.disconnect` y Starlette CANCELA la tarea que envía el cuerpo.
* **2.4**: no hay escucha del corte; es `send` el que lanza `OSError` cuando el cliente ya no está.

Y el generador del chat puede estar en dos sitios cuando llega el corte: **esperando al agente** (la cancelación salta dentro de él) o **suspendido en un
`yield`** mientras se envía un trozo (la cancelación salta en `stream_response` y nadie le llama a `aclose()`: lo cierra `ChatStreamingResponse`).
En los dos casos tiene que quedar guardado el mensaje `interrupted` con lo recibido, y cerrada la conexión con el agente.
"""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import HttpAgentsClient
from cuadre.agents import http as http_module
from tests.agents.server import Reply, ScriptedServer
from tests.agents.support import API_KEY, captured_logs
from tests.api.conftest import Signer
from tests.chat.conftest import QUESTION, stored
from tests.chat.fakes import GatedAgent, frames
from tests.support import Cast

TOKEN_PIECE = b'event: token\ndata: {"delta":"palabra "}\n\n'


async def browser_that_leaves(
    app: FastAPI,
    token: str,
    *,
    spec_version: str,
    leave_after_tokens: int,
    stall_the_send: bool,
    content: str = QUESTION,
) -> list[dict[str, Any]]:
    """Un navegador que envía el mensaje, lee `leave_after_tokens` eventos `token` y se va. Devuelve lo que la aplicación le envió."""
    body = json.dumps({"conversation_id": None, "content": content}).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": spec_version},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/chat",
        "raw_path": b"/api/chat",
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"authorization", f"Bearer {token}".encode()),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
        "state": {},
    }
    gone = asyncio.Event()
    delivered = False
    tokens = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await gone.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        nonlocal tokens
        if gone.is_set() and spec_version == "2.4":
            raise OSError("el cliente ya no está")
        sent.append(message)
        if message["type"] != "http.response.body":
            return
        tokens += message.get("body", b"").count(b"event: token")
        if tokens >= leave_after_tokens and not gone.is_set():
            gone.set()  # el navegador cierra la pestaña
            if stall_the_send and spec_version == "2.3":
                await asyncio.sleep(
                    3600
                )  # y el envío de este trozo no acaba: el generador queda suspendido en su `yield`

    async with app.router.lifespan_context(app):
        await app(scope, receive, send)  # type: ignore[arg-type]
    return sent


def leave(
    app: FastAPI,
    signer: Signer,
    cast: Cast,
    *,
    spec_version: str,
    leave_after_tokens: int = 1,
    stall_the_send: bool = False,
) -> list[dict[str, Any]]:
    return asyncio.run(
        browser_that_leaves(
            app,
            signer.token(cast.alicia),
            spec_version=spec_version,
            leave_after_tokens=leave_after_tokens,
            stall_the_send=stall_the_send,
        )
    )


def frames_text() -> str:
    return "".join(f.root.data.delta for f in frames("answer_with_citation") if f.root.event == "token")  # type: ignore[union-attr]


def only_conversation(admin: Connection[DictRow], cast: Cast) -> Any:
    rows = admin.execute("select id from public.chat_conversations where owner_id = %s", (cast.alicia.id,)).fetchall()
    assert len(rows) == 1, rows
    return rows[0]["id"]


# --- Esperando al agente (la cancelación salta dentro del generador) ------------------------------------------------------------------


def test_ac13_leaving_while_the_service_waits_for_the_agent_saves_what_arrived_as_interrupted(
    app: FastAPI,
    signer: Signer,
    cast: Cast,
    admin: Connection[DictRow],
) -> None:
    agent = GatedAgent(
        frames("answer_with_citation"), gate_after=2
    )  # la puerta no se abre nunca: el agente se queda esperando
    app.state.agents_client = agent
    with captured_logs("cuadre") as records:
        sent = leave(app, signer, cast, spec_version="2.3", leave_after_tokens=1)
    assert agent.closed.is_set(), "la conexión con el agente no se cerró"
    assert not agent.timed_out
    assert sent[0]["status"] == 200

    conversation = only_conversation(admin, cast)
    user_row, assistant_row = stored(admin, conversation)
    assert (user_row["role"], user_row["content"], user_row["status"]) == ("user", QUESTION, "complete")
    assert (assistant_row["status"], assistant_row["finish_reason"], assistant_row["has_source"]) == (
        "interrupted",
        None,
        None,
    )
    # Lo recibido hasta el corte: el primer token seguro; el segundo, si ya se había acumulado cuando llegó la cancelación.
    assert assistant_row["content"].startswith("Si el cliente es una empresa de la UE con NIF-IVA válido, ")
    assert assistant_row["content"] in ("Si el cliente es una empresa de la UE con NIF-IVA válido, ", frames_text())
    assert assistant_row["citations"] == [] and assistant_row["abstention"] is None

    (record,) = [r for r in records if r.getMessage() == "chat_stream"]
    assert record.__dict__["outcome"] == "interrupted" and record.__dict__["saved"] == "saved"
    assert QUESTION not in "".join(f"{r.getMessage()} {r.__dict__}" for r in records)


# --- Suspendido en un `yield` (nadie llama a `aclose()` salvo `ChatStreamingResponse`) -------------------------------------------------


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
def test_ac13_leaving_while_a_chunk_is_being_sent_still_saves_the_interrupted_message_and_closes_the_agent(
    app: FastAPI,
    signer: Signer,
    cast: Cast,
    admin: Connection[DictRow],
    spec_version: str,
) -> None:
    agent = GatedAgent(frames("answer_with_citation"), gate_after=99)  # nunca se frena: emite todo seguido
    app.state.agents_client = agent
    leave(app, signer, cast, spec_version=spec_version, leave_after_tokens=1, stall_the_send=True)
    assert agent.closed.is_set(), "el generador del agente no se cerró: nadie le llamó a aclose()"

    conversation = only_conversation(admin, cast)
    user_row, assistant_row = stored(admin, conversation)
    assert user_row["status"] == "complete" and assistant_row["status"] == "interrupted"
    assert assistant_row["content"].startswith("Si el cliente es una empresa de la UE con NIF-IVA válido, ")
    assert assistant_row["finish_reason"] is None and assistant_row["has_source"] is None


def test_ac13_the_interrupted_answer_is_in_the_history_with_its_mark_and_does_not_go_back_to_the_agent(
    app: FastAPI,
    signer: Signer,
    cast: Cast,
    admin: Connection[DictRow],
) -> None:
    app.state.agents_client = GatedAgent(frames("answer_with_citation"), gate_after=2)
    leave(app, signer, cast, spec_version="2.3")
    conversation = only_conversation(admin, cast)

    from fastapi.testclient import TestClient

    from cuadre.agents import FakeAgentsClient

    fake = FakeAgentsClient(chat_script=["answer_length"])
    app.state.agents_client = fake
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {signer.token(cast.alicia)}"}
        detail = client.get(f"/api/chat/conversations/{conversation}", headers=headers).json()
        assert [(m["role"], m["status"]) for m in detail["messages"]] == [
            ("user", "complete"),
            ("assistant", "interrupted"),
        ]
        reply = client.post(
            "/api/chat", headers=headers, json={"conversation_id": str(conversation), "content": "Sigue, por favor"}
        )
        assert reply.status_code == 200
    sent_to_agent = fake.chat_calls[-1].request.messages
    assert [m.content for m in sent_to_agent] == [
        "Sigue, por favor"
    ]  # ni la respuesta cortada ni la pregunta que se quedó sin respuesta


# --- Con el cliente HTTP de verdad (la conexión con el agente se cierra por el cable) ----------------------------------------------------


def test_ac13_with_the_real_http_client_the_agents_server_sees_the_browser_leave(
    app: FastAPI,
    signer: Signer,
    cast: Cast,
    admin: Connection[DictRow],
    server: ScriptedServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = {"clients": 0, "closed": 0}
    original_init, original_close = http_module.httpx.AsyncClient.__init__, http_module.httpx.AsyncClient.aclose

    def counting_init(self: Any, *args: Any, **kwargs: Any) -> None:
        opened["clients"] += 1
        original_init(self, *args, **kwargs)

    async def counting_close(self: Any) -> None:
        opened["closed"] += 1
        await original_close(self)

    monkeypatch.setattr(http_module.httpx.AsyncClient, "__init__", counting_init)
    monkeypatch.setattr(http_module.httpx.AsyncClient, "aclose", counting_close)

    server.serve(
        Reply(200, content_type="text/event-stream", chunked=True, pieces=[TOKEN_PIECE] * 150, chunk_delay_ms=20)
    )
    app.state.agents_client = HttpAgentsClient(server.url, API_KEY)
    leave(app, signer, cast, spec_version="2.3", leave_after_tokens=2)

    deadline = asyncio.run(_wait_for(lambda: server.client_gone >= 1, 5))
    assert deadline, "el servidor del agente siguió escribiendo: la conexión no se cerró"
    assert opened["clients"] == opened["closed"] >= 1
    conversation = only_conversation(admin, cast)
    assistant_row = stored(admin, conversation)[1]
    assert assistant_row["status"] == "interrupted" and assistant_row["content"].startswith("palabra palabra ")
    assert os.environ.get("DATABASE_URL")


async def _wait_for(condition: Callable[[], bool], seconds: int) -> bool:
    waiter: Callable[[], Awaitable[None]] = lambda: asyncio.sleep(0.02)  # noqa: E731
    for _ in range(int(seconds / 0.02)):
        if condition():
            return True
        await waiter()
    return condition()
