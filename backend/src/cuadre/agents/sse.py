"""Lectura de `text/event-stream` para el chat (SPEC-W-004 §5.4, D-10).

Lo que llega del agente es dato no confiable: este módulo solo hace la parte **sintáctica** (trocear en eventos con topes, descartar lo que no
se conoce y validar cada frame con el contrato). Que el orden de los frames tenga sentido lo comprueba `cuadre.chat.rules`.

El parser es incremental sobre **bytes**: una línea solo se decodifica cuando está completa, así que un carácter de varios bytes partido entre
dos trozos de red no se rompe (ningún byte de una secuencia UTF-8 de varios bytes vale `\\n` ni `\\r`). Nada de lo recibido, ni siquiera un
trozo, llega a un mensaje de error: las excepciones no llevan datos del agente.
"""

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from cuadre_contracts.chat import ChatStreamFrame

# Los siete eventos de C2. Cualquier otro (`message`, uno nuevo de una versión posterior…) se descarta sin más.
KNOWN_EVENTS = frozenset({"token", "citation", "tool_call", "abstention", "usage", "done", "error"})
TERMINAL_EVENTS = frozenset({"done", "error"})

MAX_LINE_BYTES = 32_768
MAX_EVENT_BYTES = 65_536

_EOL = re.compile(rb"\r\n|\r|\n")


class SseProtocolError(Exception):
    """El flujo no es SSE válido o se pasa de los topes. Sin datos del flujo en el mensaje."""


class InvalidFrame(Exception):
    """Un evento conocido cuyos datos no cumplen el contrato C2. Sin datos del evento en el mensaje."""


@dataclass(frozen=True, slots=True)
class RawEvent:
    name: str
    data: str


class SseParser:
    """Trocea bytes en eventos. `feed` devuelve los eventos que se completan con ese trozo."""

    def __init__(self, *, max_line_bytes: int = MAX_LINE_BYTES, max_event_bytes: int = MAX_EVENT_BYTES) -> None:
        self._max_line = max_line_bytes
        self._max_event = max_event_bytes
        self._buffer = bytearray()
        self._name = ""
        self._data: list[str] = []
        self._has_data = False
        self._event_bytes = 0

    @property
    def pending(self) -> bool:
        """¿Quedó algo sin terminar (una línea o un evento a medias)? Por la norma SSE, un evento sin línea en blanco final se descarta."""
        return bool(self._buffer) or self._has_data or bool(self._name)

    def feed(self, chunk: bytes) -> list[RawEvent]:
        self._buffer += chunk
        events: list[RawEvent] = []
        position = 0
        while True:
            match = _EOL.search(self._buffer, position)
            if match is None:
                if len(self._buffer) - position > self._max_line:
                    raise SseProtocolError("línea demasiado larga")
                break
            if match.group() == b"\r" and match.end() == len(self._buffer):
                # Un `\r` al final del trozo: puede ser el principio de `\r\n`; se espera al siguiente para saberlo.
                if match.start() - position > self._max_line:
                    raise SseProtocolError("línea demasiado larga")
                break
            line = bytes(self._buffer[position : match.start()])
            if len(line) > self._max_line:
                raise SseProtocolError("línea demasiado larga")
            position = match.end()
            event = self._line(line)
            if event is not None:
                events.append(event)
        del self._buffer[:position]
        return events

    def finish(self) -> list[RawEvent]:
        """Se acabó el flujo: un `\r` que esperaba su `\n` era un fin de línea completo. Lo demás sin cerrar sigue en `pending`."""
        return self.feed(b"\n") if self._buffer.endswith(b"\r") else []

    def _line(self, raw: bytes) -> RawEvent | None:
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise SseProtocolError("UTF-8 no válido") from None
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            return None  # comentario: se usa como latido para mantener la conexión abierta
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        self._event_bytes += len(raw)
        if self._event_bytes > self._max_event:
            raise SseProtocolError("evento demasiado grande")
        if field == "event":
            self._name = value
        elif field == "data":
            self._data.append(value)
            self._has_data = True
        # `id`, `retry` y cualquier otro campo se ignoran.
        return None

    def _dispatch(self) -> RawEvent | None:
        event = RawEvent(self._name or "message", "\n".join(self._data)) if self._has_data else None
        self._name = ""
        self._data = []
        self._has_data = False
        self._event_bytes = 0
        return event


def decode_frame(event: str, data: str) -> ChatStreamFrame | None:
    """El frame de C2 de un evento, `None` si el evento no es de los siete (se descarta) o `InvalidFrame` si lo es y sus datos no valen."""
    if event not in KNOWN_EVENTS:
        return None
    try:
        payload = json.loads(data, parse_constant=_reject_constant)
        # Se reserializa y se valida en modo JSON estricto, como el cliente de lectura: un número donde va una cadena no se admite.
        return ChatStreamFrame.model_validate_json(json.dumps({"event": event, "data": payload}), strict=True)
    except (ValueError, RecursionError, ValidationError):
        raise InvalidFrame("frame no válido") from None


def _reject_constant(_name: str) -> None:
    raise ValueError("constante JSON no admitida")


def is_terminal(frame: ChatStreamFrame) -> bool:
    return frame.root.event in TERMINAL_EVENTS


def frames_of(payload: bytes) -> list[ChatStreamFrame]:
    """Todos los frames de un flujo completo ya leído (los ejemplos del contrato). Mismo parser y mismas reglas que el cliente HTTP."""
    parser = SseParser()
    frames: list[ChatStreamFrame] = []
    for event in [*parser.feed(payload), *parser.finish()]:
        frame = decode_frame(event.name, event.data)
        if frame is not None:
            frames.append(frame)
    if parser.pending:
        raise SseProtocolError("flujo incompleto")
    return frames
