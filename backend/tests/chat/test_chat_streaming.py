"""AC-13 · `ChatStreamingResponse` cierra el generador del cuerpo aunque Starlette cancele el envío (SPEC-W-004 §5.4, D-07).

El generador del chat ya lleva su propio escudo en su `finally`; esta clase tiene que protegerse también por sí sola, porque con uvicorn la cancelación llega
mientras el generador está suspendido en un `yield` y es ELLA quien le llama a `aclose()`. Aquí se prueba con un generador que NO se protege: su limpieza
solo termina si la clase lo cierra bajo escudo.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from starlette.requests import ClientDisconnect

from cuadre.api.streaming import ChatStreamingResponse
from cuadre.chat import limits
from cuadre.chat.errors import chat_rate_limited


async def drive(response: ChatStreamingResponse, *, spec_version: str) -> list[dict[str, Any]]:
    """Un navegador que lee el primer trozo y se va; el envío de ese primer trozo no acaba nunca (como un socket lleno)."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": spec_version},
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    gone = asyncio.Event()
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        await gone.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if gone.is_set() and spec_version == "2.4":
            raise OSError("el cliente ya no está")
        sent.append(message)
        if message["type"] == "http.response.body" and not gone.is_set():
            gone.set()
            if spec_version == "2.3":
                await asyncio.sleep(3600)

    with contextlib.suppress(
        ClientDisconnect
    ):  # con la spec 2.4, Starlette lo convierte en esto cuando `send` falla con `OSError`
        await response(scope, receive, send)  # type: ignore[arg-type]
    return sent


def cleaning_body(log: list[str]) -> AsyncIterator[bytes]:
    async def body() -> AsyncIterator[bytes]:
        try:
            yield b"uno\n"
            yield b"dos\n"
            yield b"tres\n"
        finally:
            await anyio.sleep(
                0
            )  # un punto de cancelación: en un ámbito cancelado y sin escudo, esto lanza y la limpieza no termina
            await asyncio.sleep(0.01)
            log.append("limpio")

    return body()


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
def test_the_body_generator_is_always_closed_and_its_cleanup_finishes_even_if_the_send_was_cancelled(
    spec_version: str,
) -> None:
    log: list[str] = []
    response = ChatStreamingResponse(cleaning_body(log), media_type="text/event-stream")
    asyncio.run(drive(response, spec_version=spec_version))
    assert log == ["limpio"]


def test_a_stream_that_ends_normally_is_closed_too() -> None:
    log: list[str] = []

    async def run() -> list[bytes]:
        chunks: list[bytes] = []
        response = ChatStreamingResponse(cleaning_body(log), media_type="text/event-stream")

        async def receive() -> dict[str, Any]:
            await asyncio.sleep(3600)
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        await response(
            {"type": "http.get", "asgi": {"spec_version": "2.3"}, "method": "GET", "path": "/", "headers": []},
            receive,
            send,
        )  # type: ignore[arg-type]
        return chunks

    assert b"".join(asyncio.run(run())) == b"uno\ndos\ntres\n" and log == ["limpio"]


# --- `Retry-After` del 429 (acotado entre 1 y la ventana) -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "header"),
    [(1, "1"), (30, "30"), (3_599, "3599"), (3_600, "3600"), (0, "1"), (-5, "1"), (99_999, "3600")],
)
def test_the_retry_after_of_a_rate_limit_is_always_between_one_second_and_the_window(seconds: int, header: str) -> None:
    problem = chat_rate_limited(seconds)
    assert problem.status == 429 and problem.code == "chat_rate_limited" and problem.headers == {"Retry-After": header}
    assert 1 <= int(problem.headers["Retry-After"]) <= limits.MAX_RETRY_AFTER_SECONDS


def test_without_a_computed_value_the_retry_after_falls_back_to_a_minute() -> None:
    assert chat_rate_limited().headers == {"Retry-After": str(limits.RETRY_AFTER_FALLBACK_SECONDS)}
