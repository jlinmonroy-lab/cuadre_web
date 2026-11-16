"""Errores del chat en `application/problem+json` (SPEC-W-004 §5.3). `detail` en español, sin datos de la persona ni del agente."""

from uuid import UUID

from cuadre.chat import limits
from cuadre.core.errors import ProblemError


def chat_rate_limited(retry_after_seconds: int = limits.RETRY_AFTER_FALLBACK_SECONDS) -> ProblemError:
    return ProblemError(
        429,
        "chat_rate_limited",
        "Demasiados mensajes",
        "Has enviado muchos mensajes seguidos. Espera un poco y vuelve a intentarlo.",
        headers={"Retry-After": str(max(1, min(retry_after_seconds, limits.MAX_RETRY_AFTER_SECONDS)))},
    )


def conversation_not_found() -> ProblemError:
    return ProblemError(404, "conversation_not_found", "Conversación no encontrada", "No existe esa conversación.")


def message_not_found() -> ProblemError:
    return ProblemError(404, "message_not_found", "Mensaje no encontrado", "No existe ese mensaje del asistente.")


def message_empty() -> ProblemError:
    return ProblemError(422, "message_empty", "Mensaje vacío", "Escribe tu pregunta antes de enviarla.")


def message_too_long() -> ProblemError:
    return ProblemError(
        422,
        "message_too_long",
        "Mensaje demasiado largo",
        f"El mensaje no puede pasar de {limits.MAX_MESSAGE_CHARS:,} caracteres.".replace(",", "."),
    )


def agent_unavailable(conversation_id: UUID) -> ProblemError:
    """El agente no respondió antes del primer frame. Tu mensaje queda guardado; `conversation_id` permite abrir la conversación y reintentar."""
    return ProblemError(
        503,
        "agent_unavailable",
        "Asistente no disponible",
        "El asistente no está disponible ahora mismo. Tu mensaje se ha guardado: inténtalo de nuevo en unos minutos.",
        headers={"Retry-After": str(limits.RETRY_AFTER_AGENT_UNAVAILABLE)},
        extra={"conversation_id": str(conversation_id)},
    )
