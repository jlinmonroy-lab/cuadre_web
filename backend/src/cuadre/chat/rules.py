"""Reglas puras del chat (SPEC-W-004 §5.1): sin base de datos, sin red, sin reloj y sin FastAPI.

Lo que dice el agente es dato no confiable (ADR-0012, D-10): aquí se decide qué parte llega al navegador y qué se guarda, siempre acotado. Solo se
importa `cuadre_contracts` (los modelos del contrato, datos sin entrada ni salida). El código de un fallo del agente se recibe como texto para no
depender de `cuadre.agents`.
"""

from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from cuadre.chat import limits
from cuadre.chat.types import ContextRow, Outcome, OutEvent, Usage
from cuadre_contracts import ChatRequest, ChatStreamFrame
from cuadre_contracts.chat import (
    AbstentionFrame,
    CitationFrame,
    DoneFrame,
    ErrorFrame,
    TokenFrame,
    ToolCallFrame,
    UsageFrame,
)

# Las respuestas del asistente que cuentan como historial: las que terminaron y dijeron algo.
USEFUL_STATUSES = frozenset({"complete", "abstained"})

# Lo único que ve el navegador de un fallo: un código de esta lista y SU texto fijo en español. Nunca el mensaje del agente.
BROWSER_ERRORS = {
    "agent_unavailable": "El asistente no está disponible ahora mismo. Inténtalo de nuevo en unos minutos.",
    "agent_error": "El asistente ha tenido un problema al responder. Inténtalo de nuevo.",
    "tool_error": "No se han podido consultar tus datos ahora mismo. Inténtalo de nuevo.",
    "timeout": "El asistente ha tardado demasiado en responder. Inténtalo de nuevo.",
    "unavailable": "No hemos podido guardar la respuesta. Inténtalo de nuevo.",
}

# Fallos del cliente de agentes (`FailureCode`) y errores que envía el propio agente (`ChatErrorCode`) a los códigos de arriba.
_FROM_FAILURE = {
    "timeout": "timeout",
    "upstream_error": "agent_error",
    "invalid_response": "agent_error",
    "agents_unavailable": "agent_unavailable",
}
_FROM_AGENT_ERROR = {
    "timeout": "timeout",
    "tool_error": "tool_error",
    "upstream_error": "agent_error",
    "unauthorized": "agent_unavailable",
    "invalid_request": "agent_unavailable",
}


class MessageEmpty(ValueError):
    pass


class MessageTooLong(ValueError):
    pass


def clean_message(text: str) -> str:
    """El mensaje de la persona sin espacios en los extremos, o `MessageEmpty` / `MessageTooLong`."""
    message = text.strip()
    if not message:
        raise MessageEmpty
    if len(message) > limits.MAX_MESSAGE_CHARS:
        raise MessageTooLong
    return message


def title_of(text: str) -> str:
    """Los primeros 60 caracteres del primer mensaje, en una línea y sin cortar una palabra a medias."""
    line = " ".join(text.split())
    if len(line) <= limits.TITLE_CHARS:
        return line
    cut = line[: limits.TITLE_CHARS]
    if not line[limits.TITLE_CHARS].isspace() and " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip()


def context_for_agent(rows: Sequence[ContextRow]) -> list[dict[str, str]]:
    """El historial que se envía al agente: la última fila es el mensaje nuevo de la persona.

    Entran las preguntas y las respuestas que terminaron (`complete`, `abstained`); no las que fallaron o se interrumpieron. Una pregunta que se
    quedó sin respuesta útil (la sigue otra pregunta de la persona) tampoco: un «reintentar» no deja la misma pregunta dos veces. Como mucho
    `CONTEXT_MESSAGES` y empezando por una pregunta.
    """
    kept = [row for row in rows if row.role == "user" or (row.status in USEFUL_STATUSES and row.content.strip())]
    if not kept or kept[-1].role != "user":
        raise ValueError("El último mensaje del historial debe ser el de la persona.")
    result = [
        row
        for index, row in enumerate(kept)
        if index == len(kept) - 1 or not (row.role == "user" and kept[index + 1].role == "user")
    ]
    result = result[-limits.CONTEXT_MESSAGES :]
    while len(result) > 1 and result[0].role == "assistant":
        result.pop(0)
    return [{"role": row.role, "content": row.content} for row in result]


def build_request(conversation_id: UUID, rows: Sequence[ContextRow], *, has_gestor: bool, today: date) -> ChatRequest:
    """La petición a C2: sin herramientas de datos todavía (`mcp_url` nulo, sin token), SPEC-W-011 las añade."""
    return ChatRequest.model_validate(
        {
            "conversation_id": str(conversation_id),
            "messages": context_for_agent(rows),
            "locale": "es-ES",
            "user_context": {"role": "usuario", "has_gestor": has_gestor, "current_date": today.isoformat()},
            "mcp_url": None,
        }
    )


def referral_for(referral: str | None, has_gestor: bool) -> str | None:
    """D-11: la web decide a quién se deriva. Si el agente manda a un gestor que la persona no tiene, se dice «asesor»."""
    return "asesor" if referral == "gestor" and not has_gestor else referral


def error_code_for_failure(failure_code: str) -> str:
    return _FROM_FAILURE.get(failure_code, "agent_unavailable")


def has_source(citations: int, finished_tools: int) -> bool:
    """NFR-08, D-08: una respuesta tiene fuente si cita algo o se apoyó en una herramienta que terminó."""
    return citations > 0 or finished_tools > 0


class ReplyAccumulator:
    """Va recibiendo los frames del agente. `accept` devuelve lo que se reenvía al navegador; el resto es lo que se guardará.

    Los eventos terminales (`done`, `error`) no se reenvían desde aquí: los emite el servicio DESPUÉS de guardar el mensaje, con su identificador.
    """

    def __init__(self, *, has_gestor: bool) -> None:
        self._has_gestor = has_gestor
        self._parts: list[str] = []
        self._length = 0
        self.truncated = False
        self.citations: list[dict[str, Any]] = []
        self.abstention: dict[str, Any] | None = None
        self.finished_tools = 0
        self.usage = Usage()
        self.frames = 0
        self.terminal: str | None = None  # `done` o `error`
        self.finish_reason: str | None = None
        self.trace_id = ""
        self.failure: str | None = None  # el código que ve el navegador si algo falló

    @property
    def text(self) -> str:
        return "".join(self._parts)

    def fail(self, code: str) -> None:
        """El flujo se rompió (un fallo del cliente de agentes): se guarda lo recibido y se termina como `error`."""
        self.failure = code

    def accept(self, frame: ChatStreamFrame) -> list[OutEvent]:
        if self.terminal is not None:
            return []  # nada después de `done` o `error`
        self.frames += 1
        root = frame.root
        if isinstance(root, TokenFrame):
            return self._token(root.data.delta)
        if isinstance(root, CitationFrame):
            if len(self.citations) >= limits.MAX_CITATIONS:
                return []
            data = root.data.model_dump(mode="json")
            self.citations.append(data)
            return [("citation", data)]
        if isinstance(root, ToolCallFrame):
            if root.data.status == "finished":
                self.finished_tools += 1
            return [("tool_call", {"name": root.data.name[: limits.MAX_TOOL_NAME_CHARS], "status": root.data.status})]
        if isinstance(root, AbstentionFrame):
            if self.abstention is not None:
                return []  # la primera manda
            self.abstention = {
                "reason": root.data.reason.value,
                "referral": referral_for(root.data.referral, self._has_gestor),
            }
            return [("abstention", dict(self.abstention))]
        if isinstance(root, UsageFrame):
            self.usage = Usage(root.data.input_tokens, root.data.output_tokens)
            return [("usage", {"input_tokens": self.usage.input_tokens, "output_tokens": self.usage.output_tokens})]
        if isinstance(root, DoneFrame):
            self.terminal = "done"
            self.finish_reason = root.data.finish_reason.value
            self.trace_id = root.data.trace_id[:200]
            return []
        if isinstance(root, ErrorFrame):
            self.terminal = "error"
            self.failure = _FROM_AGENT_ERROR.get(root.data.code.value, "agent_error")
            return []
        return []

    def _token(self, delta: str) -> list[OutEvent]:
        room = limits.MAX_REPLY_CHARS - self._length
        if not delta:
            return []
        if room <= 0:
            self.truncated = True
            return []
        piece = delta[:room]
        if len(piece) < len(delta):
            self.truncated = True
        self._parts.append(piece)
        self._length += len(piece)
        return [("token", {"delta": piece})]

    def outcome(self) -> Outcome:
        if self.failure is not None:
            return Outcome("error", "error", None, error_code=self.failure)
        if self.terminal != "done":
            return Outcome("interrupted", None, None)
        finish = self.finish_reason
        if self.abstention is not None or finish == "abstained":
            return Outcome("abstained", "abstained", None)
        if finish == "error":
            return Outcome("error", "error", None, error_code="agent_error")
        if self.truncated and finish == "stop":
            finish = "length"
        return Outcome("complete", finish, has_source(len(self.citations), self.finished_tools))


def terminal_event(outcome: Outcome, *, message_id: UUID, trace_id: str) -> OutEvent:
    """El último evento que ve el navegador, ya con el mensaje guardado."""
    if outcome.status == "error":
        code = outcome.error_code if outcome.error_code in BROWSER_ERRORS else "agent_error"
        return ("error", {"code": code, "message": BROWSER_ERRORS[code], "message_id": str(message_id)})
    return (
        "done",
        {
            "finish_reason": outcome.finish_reason,
            "trace_id": trace_id,
            "message_id": str(message_id),
            "has_source": outcome.has_source,
            "status": outcome.status,
        },
    )


def unavailable_event(message_id: UUID) -> OutEvent:
    """Se terminó de recibir pero no se pudo guardar la respuesta."""
    return ("error", {"code": "unavailable", "message": BROWSER_ERRORS["unavailable"], "message_id": str(message_id)})
