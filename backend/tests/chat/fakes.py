"""Agentes de pruebas del chat: dobles asíncronos que se cuelgan, se rompen o dejan pasar a la prueba a su ritmo.

Los frames salen de los ejemplos del contrato (`tests.agents.support.chat_bytes`): lo que la API reenvía es lo mismo que valida el contrato.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Sequence

from cuadre.agents import AgentsError, FailureCode
from cuadre.agents.fake import ChatCall
from cuadre.agents.sse import frames_of
from cuadre_contracts import ChatRequest, ChatStreamFrame
from tests.agents.support import chat_bytes

POLL_SECONDS = 0.01
GATE_SECONDS = 8


def frames(name: str) -> list[ChatStreamFrame]:
    return frames_of(chat_bytes(name))


class TrackedStream:
    """Un generador asíncrono que apunta cuándo alguien lo cierra DE VERDAD (`aclose()`). El bucle de eventos, al terminar, también recoge los
    generadores sin cerrar; sin esto una prueba no distinguiría «lo cerró el servicio» de «lo recogió el recolector después»."""

    def __init__(self, inner: AsyncIterator[ChatStreamFrame], explicit: threading.Event) -> None:
        self._inner = inner
        self._explicit = explicit

    def __aiter__(self) -> "TrackedStream":
        return self

    async def __anext__(self) -> ChatStreamFrame:
        return await self._inner.__anext__()

    async def aclose(self) -> None:
        self._explicit.set()
        await self._inner.aclose()  # type: ignore[attr-defined]


class GatedAgent:
    """Emite los primeros `gate_after` frames, espera a que la prueba abra la puerta y emite el resto.

    Si la API acumulara el flujo, la prueba no vería nada antes de abrir la puerta. Si la puerta no se abre en 8 s, el agente falla (y `timed_out`
    lo dice) para que una prueba mal escrita no se cuelgue.
    """

    def __init__(self, source: Sequence[ChatStreamFrame], *, gate_after: int) -> None:
        self.source = list(source)
        self.gate_after = gate_after
        self.gate = threading.Event()
        self.timed_out = False
        self.reached_gate = threading.Event()
        self.closed = (
            threading.Event()
        )  # el generador se cerró (por `aclose()`, por cancelación o porque el bucle lo recogió)
        self.closed_explicitly = (
            threading.Event()
        )  # alguien llamó a `aclose()`: no basta con que el recolector lo limpie después
        self.chat_calls: list[ChatCall] = []

    def stream_chat(self, request: ChatRequest, *, request_id: str, user_token: str | None = None) -> "TrackedStream":
        self.chat_calls.append(ChatCall(request, request_id, user_token is not None))
        return TrackedStream(self._generate(), self.closed_explicitly)

    async def _generate(self) -> AsyncIterator[ChatStreamFrame]:
        try:
            for index, frame in enumerate(self.source):
                if index == self.gate_after:
                    self.reached_gate.set()
                    for _ in range(int(GATE_SECONDS / POLL_SECONDS)):
                        if self.gate.is_set():
                            break
                        await asyncio.sleep(POLL_SECONDS)
                    else:
                        self.timed_out = True
                        raise AgentsError(FailureCode.timeout)
                yield frame
        finally:
            self.closed.set()


class BrokenAgent:
    """Emite `before` frames y entonces falla con `error` (por defecto, un `RuntimeError` inesperado)."""

    def __init__(self, source: Sequence[ChatStreamFrame] = (), *, error: BaseException | None = None) -> None:
        self.source = list(source)
        self.error = error if error is not None else RuntimeError("fallo inesperado de prueba")
        self.chat_calls: list[ChatCall] = []

    async def stream_chat(
        self, request: ChatRequest, *, request_id: str, user_token: str | None = None
    ) -> AsyncIterator[ChatStreamFrame]:
        self.chat_calls.append(ChatCall(request, request_id, user_token is not None))
        for frame in self.source:
            yield frame
        raise self.error


class EmptyAgent:
    """Se cierra sin emitir un solo frame."""

    def __init__(self) -> None:
        self.chat_calls: list[ChatCall] = []

    async def stream_chat(
        self, request: ChatRequest, *, request_id: str, user_token: str | None = None
    ) -> AsyncIterator[ChatStreamFrame]:
        self.chat_calls.append(ChatCall(request, request_id, user_token is not None))
        return
        yield  # pragma: no cover - hace de esto un generador asíncrono
