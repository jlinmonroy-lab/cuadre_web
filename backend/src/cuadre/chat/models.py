"""Modelos de la API del chat (SPEC-W-004 §5.3). De ellos sale el cliente TypeScript.

El flujo `POST /api/chat` no se describe aquí (ADR-0011): sus eventos viven en `frontend/src/lib/chat.ts` y en la spec.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cuadre.chat.limits import MAX_BODY_CHARS

MessageStatus = Literal["complete", "abstained", "error", "interrupted"]
FeedbackReason = Literal["incorrect", "no_source", "not_helpful", "other"]


class ChatBody(BaseModel):
    conversation_id: UUID | None = Field(
        default=None, description="La conversación a la que se añade el mensaje; `null` crea una nueva con este mensaje"
    )
    content: str = Field(
        max_length=MAX_BODY_CHARS,
        description="El mensaje de la persona: de 1 a 2.000 caracteres (`message_empty` y `message_too_long` si no)",
    )


class CitationOut(BaseModel):
    id: str
    title: str
    publisher: str
    url: str = Field(description="Solo se enlaza si empieza por `https://` (D-10)")
    valid_as_of: date | None
    quote: str | None = None


class AbstentionOut(BaseModel):
    reason: Literal["no_source", "professional_judgment", "out_of_scope"]
    referral: Literal["gestor", "asesor"] | None = Field(
        description="A quién se deriva, ya corregido según tenga la persona gestor o no"
    )


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str = Field(description="Texto plano: no es HTML ni Markdown (D-10)")
    status: MessageStatus
    finish_reason: Literal["stop", "abstained", "length", "error"] | None
    trace_id: str | None
    has_source: bool | None = Field(
        description="NFR-08: `false` si una respuesta terminó sin ninguna cita ni herramienta; `null` si no se evalúa"
    )
    citations: list[CitationOut]
    abstention: AbstentionOut | None
    created_at: datetime
    rating: Literal["up", "down"] | None = Field(description="La valoración de la persona, si la hay")
    reason: FeedbackReason | None


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    last_message_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationSummary] = Field(description="Por última actividad, la más reciente primero")


class ConversationDetail(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    last_message_at: datetime
    messages: list[MessageOut] = Field(description="En orden cronológico; si son demasiados, los más recientes")


class FeedbackBody(BaseModel):
    rating: Literal["up", "down"]
    reason: FeedbackReason | None = Field(
        default=None, description="Obligatorio con `down` y nulo con `up` (lista cerrada, sin texto libre)"
    )

    @model_validator(mode="after")
    def reason_matches_rating(self) -> "FeedbackBody":
        if self.rating == "down" and self.reason is None:
            raise ValueError("Una valoración negativa necesita un motivo.")
        if self.rating == "up" and self.reason is not None:
            raise ValueError("Una valoración positiva no lleva motivo.")
        return self


class FeedbackOut(BaseModel):
    message_id: UUID
    rating: Literal["up", "down"]
    reason: FeedbackReason | None
