"""Contrato 2 · Chatbot: POST {AGENTS_BASE_URL}/v1/chat (respuesta SSE).

El frontend solo habla con cuadre-web (`POST /api/chat`). El backend reenvía aquí el historial
con dos credenciales distintas, nunca la service key de Supabase:

  Authorization: Bearer <AGENTS_API_KEY>      credencial de servicio web -> agentes
  X-User-Token:  <token MCP derivado>         JWT corto (aud=cuadre-mcp, scope=mcp:read) que el agente
                                              reenvía tal cual al servidor MCP de solo lectura

Cada frame SSE es `event: <nombre>` + `data: <json>`; aquí se modela como {event, data}.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, RootModel

from .common import ContractModel, Cost, Locale, ResponseModel


class ChatMessage(ContractModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class UserContext(ContractModel):
    role: Literal["usuario", "gestor"] = Field(
        description="Rol de quien pregunta. Solo el rol «usuario» recibe herramientas de datos."
    )
    has_gestor: bool = Field(description="Si el usuario tiene un gestor vinculado: decide a quién se deriva.")
    current_date: date = Field(description="Fecha de hoy en Europe/Madrid, para resolver «este año» o «este trimestre».")


class ChatRequest(ContractModel):
    conversation_id: UUID
    messages: list[ChatMessage] = Field(min_length=1, max_length=50, description="Historial en orden cronológico.")
    locale: Locale = "es-ES"
    user_context: UserContext
    mcp_url: HttpUrl | None = Field(
        description="URL del servidor MCP de solo lectura. null cuando el rol no recibe herramientas de datos."
    )


class AbstentionReason(StrEnum):
    no_source = "no_source"
    professional_judgment = "professional_judgment"
    out_of_scope = "out_of_scope"


class FinishReason(StrEnum):
    stop = "stop"
    abstained = "abstained"
    length = "length"
    error = "error"


class ChatErrorCode(StrEnum):
    unauthorized = "unauthorized"
    invalid_request = "invalid_request"
    upstream_error = "upstream_error"
    tool_error = "tool_error"
    timeout = "timeout"


class TokenData(ResponseModel):
    delta: str


class CitationData(ResponseModel):
    id: str
    title: str
    publisher: str = Field(description="Organismo emisor de la fuente oficial, por ejemplo AEAT o BOE.")
    url: HttpUrl
    valid_as_of: date | None = Field(description="Fecha de vigencia del documento en la base de conocimiento.")
    quote: str | None = Field(default=None, max_length=500)


class ToolCallData(ResponseModel):
    name: str
    status: Literal["started", "finished", "failed"]


class AbstentionData(ResponseModel):
    reason: AbstentionReason
    referral: Literal["gestor", "asesor"] | None = Field(
        description=(
            "A quién se deriva. Obligatorio cuando reason es professional_judgment: «gestor» solo si "
            "user_context.has_gestor es true; en otro caso, «asesor»."
        )
    )


class UsageData(ResponseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_eur: Cost | None = None


class DoneData(ResponseModel):
    finish_reason: FinishReason
    trace_id: str


class ErrorData(ResponseModel):
    code: ChatErrorCode
    message: str


class TokenFrame(ResponseModel):
    event: Literal["token"] = "token"
    data: TokenData


class CitationFrame(ResponseModel):
    event: Literal["citation"] = "citation"
    data: CitationData


class ToolCallFrame(ResponseModel):
    event: Literal["tool_call"] = "tool_call"
    data: ToolCallData


class AbstentionFrame(ResponseModel):
    event: Literal["abstention"] = "abstention"
    data: AbstentionData


class UsageFrame(ResponseModel):
    event: Literal["usage"] = "usage"
    data: UsageData


class DoneFrame(ResponseModel):
    event: Literal["done"] = "done"
    data: DoneData


class ErrorFrame(ResponseModel):
    event: Literal["error"] = "error"
    data: ErrorData


class ChatStreamFrame(
    RootModel[
        Annotated[
            TokenFrame | CitationFrame | ToolCallFrame | AbstentionFrame | UsageFrame | DoneFrame | ErrorFrame,
            Field(discriminator="event"),
        ]
    ]
):
    """Un frame de la respuesta SSE. El flujo termina con `done` o con `error`."""
