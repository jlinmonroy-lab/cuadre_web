"""Cliente HTTP del servicio de agentes (ADR-0012, SPEC-W-002 §5.4): `POST {AGENTS_BASE_URL}/v1/extract`.

Solo lleva la clave del servicio de agentes. Nunca la service key de Supabase ni el JWT de la persona (un test lo comprueba mirando
lo que recibe el servidor, y otro que este paquete no puede importarlos). La URL firmada del documento viaja en el cuerpo, que no se
registra. Nada de lo que devuelve el agente (cuerpo, mensaje, texto de un error de validación) llega a un registro ni a una excepción.

Tiempos en enteros (milisegundos y nanosegundos): el presupuesto de la lectura es de 45 s **en total**, incluido el reintento.
"""

import logging
import time
from collections.abc import Callable

import httpx2 as httpx
from pydantic import ValidationError

from cuadre.agents.errors import AgentsError, FailureCode, error_from_agent
from cuadre_contracts import ExtractRequest, ExtractResponse
from cuadre_contracts.extract import AgentError

logger = logging.getLogger("cuadre.agents")

CONTRACT_VERSION = "1"
EXTRACT_PATH = "/v1/extract"
DEFAULT_TIMEOUT_MS = 45_000
MAX_RESPONSE_BYTES = 1_048_576  # una lectura son unos pocos KB; más de 1 MiB no es una lectura
RETRY_PAUSE_MS = 500  # pausa ante un error de conexión o un 502 sin `Retry-After`
MAX_RETRY_AFTER_MS = 5_000  # si el servicio pide esperar más, no se reintenta
MIN_RETRY_BUDGET_MS = 5_000  # un reintento solo se hace si, tras la pausa, queda tiempo para que pueda acabar


def _sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000)


class _DeadlineExceeded(Exception):
    pass


class _ConnectionFailed(Exception):
    pass


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


class HttpAgentsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        sleep: Callable[[int], None] = _sleep_ms,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._endpoint = base_url.rstrip("/") + EXTRACT_PATH
        self._api_key = api_key
        self._timeout_ms = timeout_ms
        self._sleep = sleep
        self._clock_ns = clock_ns

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
