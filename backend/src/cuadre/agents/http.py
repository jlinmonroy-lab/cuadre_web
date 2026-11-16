"""Cliente HTTP del servicio de agentes (ADR-0012): `POST {AGENTS_BASE_URL}/v1/extract` (C1, SPEC-W-002 §5.4) y `POST {AGENTS_BASE_URL}/v1/chat` (C2, SPEC-W-004).

Solo lleva la clave del servicio de agentes (y, en el chat con herramientas, el token MCP derivado de la persona, ADR-0013). Nunca la service key
de Supabase ni el JWT de la persona (un test lo comprueba mirando lo que recibe el servidor, y otro que este paquete no puede importarlos). La
URL firmada del documento y el texto del chat viajan en el cuerpo, que no se registra. Nada de lo que devuelve el agente (cuerpo, mensaje, texto
de un error de validación, frames) llega a un registro ni a una excepción.

Tiempos en enteros (milisegundos y nanosegundos): el presupuesto de la lectura es de 45 s **en total**, incluido el reintento; el del chat, de 15 s
hasta el primer frame y 90 s en total.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass

import httpx2 as httpx
from pydantic import ValidationError

from cuadre.agents.client import check_user_token
from cuadre.agents.errors import AgentsError, FailureCode, error_from_agent
from cuadre.agents.sse import (
    MAX_EVENT_BYTES,
    MAX_LINE_BYTES,
    InvalidFrame,
    SseParser,
    SseProtocolError,
    decode_frame,
    is_terminal,
)
from cuadre_contracts import ChatRequest, ChatStreamFrame, ExtractRequest, ExtractResponse
from cuadre_contracts.extract import AgentError

logger = logging.getLogger("cuadre.agents")

CONTRACT_VERSION = "1"
EXTRACT_PATH = "/v1/extract"
CHAT_PATH = "/v1/chat"
DEFAULT_TIMEOUT_MS = 45_000
MAX_RESPONSE_BYTES = 1_048_576  # una lectura son unos pocos KB; más de 1 MiB no es una lectura
RETRY_PAUSE_MS = 500  # pausa ante un error de conexión o un 502 sin `Retry-After`
MAX_RETRY_AFTER_MS = 5_000  # si el servicio pide esperar más, no se reintenta
MIN_RETRY_BUDGET_MS = 5_000  # un reintento solo se hace si, tras la pausa, queda tiempo para que pueda acabar

# Chat (SPEC-W-004 D-12). Viven aquí y no en `cuadre.chat`: este paquete no puede importar de él.
FIRST_FRAME_TIMEOUT_MS = (
    15_000  # desde que se envía la petición hasta el primer frame válido (NFR-01: primer token p95 ≤ 2 s)
)
TOTAL_TIMEOUT_MS = 90_000  # el flujo entero
MAX_STREAM_BYTES = (
    2_097_152  # una respuesta son ≤ 8.000 caracteres más el envoltorio de cada frame; más de 2 MiB no es una respuesta
)


def _sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000)


async def _async_sleep_ms(ms: int) -> None:
    await asyncio.sleep(ms / 1000)


class _DeadlineExceeded(Exception):
    pass


class _ConnectionFailed(Exception):
    pass


class _ChatRetry(Exception):
    """El intento falló antes de recibir un solo byte del cuerpo y el motivo admite un reintento (si queda presupuesto)."""

    def __init__(self, pause_ms: int, status: int | None, error: AgentsError) -> None:
        super().__init__()
        self.pause_ms = pause_ms
        self.status = status
        self.error = error


@dataclass(slots=True)
class _ChatStats:
    """Lo único que se registra de un flujo: cifras, nunca contenido."""

    status: int | None = None
    frames: int = 0
    dropped: int = 0
    stream_bytes: int = 0
    first_frame_ms: int | None = None
    terminal: str | None = None
    trace_id: str | None = None


class _Reply:
    __slots__ = ("payload", "retry_after_ms", "status")

    def __init__(self, status: int, retry_after_ms: int | None, payload: bytes) -> None:
        self.status = status
        self.retry_after_ms = retry_after_ms
        self.payload = payload


def _retry_after_ms(value: str | None) -> int | None:
    """Solo segundos enteros (`Retry-After: 2`); una fecha HTTP o un valor raro cuentan como ausente."""
    if value is None:
        return None
    value = value.strip()
    return int(value) * 1000 if value.isascii() and value.isdigit() else None


def _retry_pause_ms(status: int, retry_after_ms: int | None) -> int | None:
    """Pausa antes del reintento, o `None` si esa respuesta no se reintenta."""
    if status not in (429, 502):
        return None
    if retry_after_ms is None:
        return RETRY_PAUSE_MS if status == 502 else None  # un 429 sin `Retry-After` no dice cuánto esperar
    return retry_after_ms if retry_after_ms <= MAX_RETRY_AFTER_MS else None


def _is_event_stream(response: httpx.Response) -> bool:
    return response.headers.get("content-type", "").split(";")[0].strip().lower() == "text/event-stream"


class HttpAgentsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        sleep: Callable[[int], None] = _sleep_ms,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        first_frame_timeout_ms: int = FIRST_FRAME_TIMEOUT_MS,
        total_timeout_ms: int = TOTAL_TIMEOUT_MS,
        max_stream_bytes: int = MAX_STREAM_BYTES,
        max_line_bytes: int = MAX_LINE_BYTES,
        max_event_bytes: int = MAX_EVENT_BYTES,
        async_sleep: Callable[[int], Awaitable[None]] = _async_sleep_ms,
    ) -> None:
        self._endpoint = base_url.rstrip("/") + EXTRACT_PATH
        self._chat_endpoint = base_url.rstrip("/") + CHAT_PATH
        self._api_key = api_key
        self._timeout_ms = timeout_ms
        self._sleep = sleep
        self._clock_ns = clock_ns
        self._first_frame_timeout_ms = first_frame_timeout_ms
        self._total_timeout_ms = total_timeout_ms
        self._max_stream_bytes = max_stream_bytes
        self._max_line_bytes = max_line_bytes
        self._max_event_bytes = max_event_bytes
        self._async_sleep = async_sleep

    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        body = request.model_dump_json().encode()
        started = self._clock_ns()
        deadline = started + self._timeout_ms * 1_000_000
        attempt = 0
        while True:
            attempt += 1
            try:
                reply = self._post(body, request_id, deadline)
            except _DeadlineExceeded:
                raise self._failed(request_id, attempt, started, FailureCode.timeout, None) from None
            except httpx.TimeoutException:
                raise self._failed(request_id, attempt, started, FailureCode.timeout, None) from None
            except _ConnectionFailed:
                if attempt == 1 and self._can_retry(deadline, RETRY_PAUSE_MS):
                    self._retrying(request_id, attempt, None, RETRY_PAUSE_MS)
                    continue
                raise self._failed(request_id, attempt, started, FailureCode.agents_unavailable, None) from None
            except httpx.TransportError:
                raise self._failed(request_id, attempt, started, FailureCode.agents_unavailable, None) from None

            if reply.status == 200:
                return self._parse(reply, request_id, attempt, started)

            pause = _retry_pause_ms(reply.status, reply.retry_after_ms)
            if attempt == 1 and pause is not None and self._can_retry(deadline, pause):
                self._retrying(request_id, attempt, reply.status, pause)
                continue

            error = error_from_agent(reply.status, self._parse_error(reply.payload))
            if reply.status == 401:
                # Credencial rechazada: es un error de configuración nuestro, no del documento. La persona verá el mensaje genérico.
                logger.error("agents_auth_rejected", extra={"request_id": request_id, "status": 401})
            raise self._failed(request_id, attempt, started, error.code, error)

    # --- Una petición HTTP -----------------------------------------------------------------------------------------------

    def _post(self, body: bytes, request_id: str, deadline: int) -> _Reply:
        remaining_ms = (deadline - self._clock_ns()) // 1_000_000
        if remaining_ms <= 0:
            raise _DeadlineExceeded
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Cuadre-Contract-Version": CONTRACT_VERSION,
            "X-Request-Id": request_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Una conexión por llamada (cada una es independiente; no hay nada que cerrar entre invocaciones de una función sin estado),
        # sin redirecciones y sin proxies del entorno: la clave del servicio solo va a la URL configurada.
        client = httpx.Client(
            timeout=httpx.Timeout(remaining_ms / 1000),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=0),
        )
        try:
            with client, client.stream("POST", self._endpoint, content=body, headers=headers) as response:
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload += chunk
                    if len(payload) > MAX_RESPONSE_BYTES:
                        return _Reply(
                            response.status_code, None, b""
                        )  # se descarta: no se parsea un cuerpo desmesurado
                    if self._clock_ns() >= deadline:
                        raise _DeadlineExceeded
                return _Reply(
                    response.status_code, _retry_after_ms(response.headers.get("retry-after")), bytes(payload)
                )
        except httpx.ConnectError:
            raise _ConnectionFailed from None

    def _can_retry(self, deadline: int, pause_ms: int) -> bool:
        return (deadline - self._clock_ns()) // 1_000_000 - pause_ms >= MIN_RETRY_BUDGET_MS

    def _retrying(self, request_id: str, attempt: int, status: int | None, pause_ms: int) -> None:
        logger.warning(
            "agents_extract_retry",
            extra={"request_id": request_id, "attempt": attempt, "status": status, "pause_ms": pause_ms},
        )
        self._sleep(pause_ms)

    # --- Respuestas ------------------------------------------------------------------------------------------------------

    def _parse(self, reply: _Reply, request_id: str, attempt: int, started: int) -> ExtractResponse:
        try:
            # strict: un número donde va una cadena, una fecha como entero o `"true"` como booleano no se admiten.
            response = ExtractResponse.model_validate_json(reply.payload, strict=True)
        except ValidationError:
            # `from None` y sin registrar el texto: un ValidationError incluye los datos recibidos.
            raise self._failed(request_id, attempt, started, FailureCode.invalid_response, None, status=200) from None
        logger.info(
            "agents_extract",
            extra={
                "request_id": request_id,
                "attempt": attempt,
                "status": 200,
                "outcome": "ok",
                "agent_trace_id": response.trace_id[:200],
                "duration_ms": (self._clock_ns() - started) // 1_000_000,
            },
        )
        return response

    @staticmethod
    def _parse_error(payload: bytes) -> AgentError | None:
        try:
            return AgentError.model_validate_json(payload, strict=True)
        except ValidationError:
            return None

    def _failed(
        self,
        request_id: str,
        attempt: int,
        started: int,
        code: FailureCode,
        error: AgentsError | None,
        *,
        status: int | None = None,
    ) -> AgentsError:
        """Registra el fallo (sin datos del documento ni del agente) y devuelve el error que hay que lanzar."""
        result = error or AgentsError(code, http_status=status)
        logger.warning(
            "agents_extract",
            extra={
                "request_id": request_id,
                "attempt": attempt,
                "status": result.http_status,
                "outcome": code.value,
                "agent_trace_id": result.trace_id,
                "duration_ms": (self._clock_ns() - started) // 1_000_000,
            },
        )
        return result

    # --- Chat (C2, SPEC-W-004) -------------------------------------------------------------------------------------------

    async def stream_chat(
        self, request: ChatRequest, *, request_id: str, user_token: str | None = None
    ) -> AsyncIterator[ChatStreamFrame]:
        check_user_token(request, user_token)
        body = request.model_dump_json().encode()
        started = self._clock_ns()
        total_deadline = started + self._total_timeout_ms * 1_000_000
        first_deadline = min(total_deadline, started + self._first_frame_timeout_ms * 1_000_000)
        stats = _ChatStats()
        attempt = 0
        outcome = "cancelled"  # si el generador se cierra antes de acabar (el navegador cortó), así queda registrado
        try:
            while True:
                attempt += 1
                try:
                    attempt_frames = self._chat_attempt(
                        body, request_id, user_token, started, total_deadline, first_deadline, stats
                    )
                    async with aclosing(attempt_frames) as frames:
                        async for frame in frames:
                            yield frame
                    outcome = "ok"
                    return
                except _ChatRetry as retry:
                    # Solo se llega aquí antes de recibir un byte del cuerpo: nunca se reintenta con el flujo empezado.
                    if attempt == 1 and self._can_retry(first_deadline, retry.pause_ms):
                        logger.warning(
                            "agents_chat_retry",
                            extra={
                                "request_id": request_id,
                                "attempt": attempt,
                                "status": retry.status,
                                "pause_ms": retry.pause_ms,
                            },
                        )
                        await self._async_sleep(retry.pause_ms)
                        continue
                    raise retry.error from None
        except AgentsError as error:
            outcome = error.code.value
            stats.status = error.http_status if error.http_status is not None else stats.status
            raise
        finally:
            self._chat_logged(request_id, attempt, started, stats, outcome)

    async def _chat_attempt(
        self,
        body: bytes,
        request_id: str,
        user_token: str | None,
        started: int,
        total_deadline: int,
        first_deadline: int,
        stats: _ChatStats,
    ) -> AsyncIterator[ChatStreamFrame]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Cuadre-Contract-Version": CONTRACT_VERSION,
            "X-Request-Id": request_id,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Accept-Encoding": "identity",  # un flujo comprimido por el camino se acumula en un búfer y llega de golpe
        }
        if user_token is not None:
            headers["X-User-Token"] = user_token
        # Sin redirecciones ni proxies del entorno, y sin plazo de httpx: los plazos los pone `_within` en cada espera, nunca a lo largo de un `yield`.
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(None),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=0),
        )
        response: httpx.Response | None = None
        try:
            request = client.build_request("POST", self._chat_endpoint, content=body, headers=headers)
            try:
                response = await self._within(client.send(request, stream=True), first_deadline)
            except httpx.ConnectError:
                raise _ChatRetry(RETRY_PAUSE_MS, None, AgentsError(FailureCode.agents_unavailable)) from None
            stats.status = response.status_code
            if response.status_code != 200:
                payload = await self._error_body(response, first_deadline)
                error = error_from_agent(response.status_code, self._parse_error(payload))
                if response.status_code == 401:
                    logger.error("agents_auth_rejected", extra={"request_id": request_id, "status": 401})
                pause = _retry_pause_ms(response.status_code, _retry_after_ms(response.headers.get("retry-after")))
                if pause is not None:
                    raise _ChatRetry(pause, response.status_code, error)
                raise error
            if not _is_event_stream(response):
                raise AgentsError(FailureCode.invalid_response, http_status=200)
            async for frame in self._chat_frames(response, started, total_deadline, first_deadline, stats):
                yield frame
        except (_DeadlineExceeded, httpx.TimeoutException):
            raise AgentsError(FailureCode.timeout, http_status=stats.status) from None
        except (SseProtocolError, InvalidFrame):
            # Sin el texto del error: lo que viene del agente no llega a ninguna excepción ni registro.
            raise AgentsError(FailureCode.invalid_response, http_status=200) from None
        except httpx.TransportError:
            raise AgentsError(FailureCode.agents_unavailable, http_status=stats.status) from None
        finally:
            if response is not None:
                await response.aclose()
            await client.aclose()

    async def _chat_frames(
        self, response: httpx.Response, started: int, total_deadline: int, first_deadline: int, stats: _ChatStats
    ) -> AsyncIterator[ChatStreamFrame]:
        parser = SseParser(max_line_bytes=self._max_line_bytes, max_event_bytes=self._max_event_bytes)
        chunks = response.aiter_bytes()
        try:
            while True:
                # Hasta el primer frame válido manda el plazo corto; los latidos y los eventos desconocidos no lo alargan.
                chunk = await self._read(chunks, total_deadline if stats.frames else first_deadline)
                if chunk is None:
                    events = parser.finish()
                else:
                    stats.stream_bytes += len(chunk)
                    if stats.stream_bytes > self._max_stream_bytes:
                        raise SseProtocolError("flujo demasiado largo")
                    events = parser.feed(chunk)
                for event in events:
                    frame = decode_frame(event.name, event.data)
                    if frame is None:
                        stats.dropped += 1
                        continue
                    stats.frames += 1
                    if stats.first_frame_ms is None:
                        stats.first_frame_ms = (self._clock_ns() - started) // 1_000_000
                    yield frame
                    if is_terminal(frame):
                        stats.terminal = frame.root.event
                        if frame.root.event == "done":
                            stats.trace_id = frame.root.data.trace_id[:200]  # type: ignore[union-attr]
                        return  # lo que viniera después de `done` o `error` se ignora; la conexión se cierra al salir
                if chunk is None:
                    # El flujo se cerró sin `done` ni `error`: una respuesta a medias no es una respuesta.
                    raise AgentsError(FailureCode.invalid_response, http_status=200)
        finally:
            await chunks.aclose()

    async def _error_body(self, response: httpx.Response, until_ns: int) -> bytes:
        payload = bytearray()
        chunks = response.aiter_bytes()
        try:
            while (chunk := await self._read(chunks, until_ns)) is not None:
                payload += chunk
                if len(payload) > MAX_RESPONSE_BYTES:
                    return b""  # se descarta: no se parsea un cuerpo desmesurado
        finally:
            await chunks.aclose()
        return bytes(payload)

    async def _read(self, chunks: AsyncIterator[bytes], until_ns: int) -> bytes | None:
        """El siguiente trozo del cuerpo, o `None` si el cuerpo terminó."""
        try:
            return await self._within(anext(chunks), until_ns)
        except StopAsyncIteration:
            return None

    async def _within[T](self, awaitable: Awaitable[T], until_ns: int) -> T:
        """Espera `awaitable` como mucho hasta `until_ns`. El `timeout` solo abarca esta espera de red, nunca un `yield` hacia quien nos consume."""
        remaining_ms = (until_ns - self._clock_ns()) // 1_000_000
        if remaining_ms <= 0:
            if asyncio.iscoroutine(awaitable):
                awaitable.close()  # no se llegó a esperar: evita el aviso de «coroutine was never awaited»
            raise _DeadlineExceeded
        try:
            async with asyncio.timeout(remaining_ms / 1000):
                return await awaitable
        except TimeoutError:
            raise _DeadlineExceeded from None

    def _chat_logged(self, request_id: str, attempt: int, started: int, stats: _ChatStats, outcome: str) -> None:
        logger.log(
            logging.INFO if outcome in ("ok", "cancelled") else logging.WARNING,
            "agents_chat",
            extra={
                "request_id": request_id,
                "attempt": attempt,
                "status": stats.status,
                "outcome": outcome,
                "terminal": stats.terminal,
                "frames": stats.frames,
                "dropped_events": stats.dropped,
                "stream_bytes": stats.stream_bytes,
                "agent_trace_id": stats.trace_id,
                "first_frame_ms": stats.first_frame_ms,
                "duration_ms": (self._clock_ns() - started) // 1_000_000,
            },
        )
