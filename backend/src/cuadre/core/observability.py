"""Registro estructurado y contexto de petición (SPEC-W-001 T-13).

Una línea JSON por petición con `request_id`, `user_id`, ruta (la plantilla, nunca la query), código y duración. NUNCA se registran
cabeceras, tokens, contraseñas, correos, IBAN ni URLs firmadas.

El middleware es ASGI puro (no `BaseHTTPMiddleware`): no interfiere con respuestas en streaming (SSE del chat) y es donde se
resuelven los 500, para que también lleven `X-Request-Id` y las cabeceras de CORS.
"""

import json
import logging
import re
import time
import uuid
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cuadre.core.errors import internal_error_response

logger = logging.getLogger("cuadre.request")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_STANDARD_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def __init__(self, *, include_traceback: bool = False) -> None:
        super().__init__()
        self.include_traceback = include_traceback

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD_RECORD_FIELDS})
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            if self.include_traceback:
                # Solo en local: el texto de una excepción puede llevar datos (p. ej. el DETAIL de un error de PostgreSQL).
                payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str, *, include_traceback: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(include_traceback=include_traceback))
    root = logging.getLogger("cuadre")
    root.handlers = [handler]
    root.setLevel(level.upper())
    root.propagate = False
    # El registro de accesos de uvicorn imprime la línea de petición CON su query string, que podría llevar un token. El de la
    # aplicación (RequestContextMiddleware) registra la ruta sin query. uvicorn configura su logging antes de importar la
    # aplicación, así que esto se aplica después y prevalece, se arranque como se arranque.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        status = 500
        started = False
        began = time.perf_counter_ns()

        async def send_with_id(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-Id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:  # noqa: BLE001 - último recurso: nada inesperado sale como traza
            logger.error(
                "unhandled_exception", extra={"request_id": request_id, "exc_type": type(exc).__name__}, exc_info=True
            )
            if not started:
                await internal_error_response(request_id)(scope, receive, send_with_id)
        finally:
            route = scope.get("route")
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "route": getattr(route, "path", None) or "-",
                    "status": status,
                    "user_id": scope.get("state", {}).get("user_id"),
                    "duration_ms": (time.perf_counter_ns() - began) // 1_000_000,
                },
            )
