"""Tipos puros del chat (sin Pydantic propio ni base de datos)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cuadre_contracts import ChatRequest


@dataclass(frozen=True, slots=True)
class ContextRow:
    """Un mensaje de la conversación tal como lo guarda la base de datos, en orden cronológico."""

    role: str  # `user` o `assistant`
    content: str
    status: str  # `complete`, `abstained`, `error` o `interrupted`


@dataclass(frozen=True, slots=True)
class Outcome:
    """Cómo terminó una respuesta y qué se guarda de ella."""

    status: str  # `complete`, `abstained`, `error` o `interrupted`
    finish_reason: str | None
    has_source: bool | None
    error_code: str | None = None  # el código que ve el navegador si terminó en `error`


@dataclass(slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


# Un evento hacia el navegador: nombre y datos (ya sin nada que no deba salir).
OutEvent = tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Prepared:
    """Lo que deja el primer paso: el mensaje de la persona guardado y la petición lista para el agente."""

    conversation_id: UUID
    user_message_id: UUID
    request: ChatRequest
    has_gestor: bool
