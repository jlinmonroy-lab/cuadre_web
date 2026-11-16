"""El chat con el asistente (SPEC-W-004 §5.3). Solo el rol `usuario` (D-01).

`POST /api/chat` es un flujo `text/event-stream`. No se declara en el esquema OpenAPI como tal (ADR-0011: el cliente usa `fetch` y los eventos están en
`frontend/src/lib/chat.ts`), y `response_class=Response` evita que FastAPI lo describa. Usa `require_role_detached`: la conexión de la base de datos no
se retiene mientras llega el flujo (cada paso abre su transacción corta en `ChatService`).
"""

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from starlette.responses import Response

from cuadre.agents import AgentsClient
from cuadre.api.streaming import ChatStreamingResponse
from cuadre.chat.models import (
    ChatBody,
    ConversationDetail,
    ConversationList,
    FeedbackBody,
    FeedbackOut,
)
from cuadre.chat.service import ChatService
from cuadre.core.auth import CurrentUser, require_role_detached
from cuadre.core.clock import Clock
from cuadre.core.errors import ProblemDetails, request_id_of
from cuadre.core.routing import new_router

router = new_router(tags=["asistente"])

Usuario = Annotated[CurrentUser, Depends(require_role_detached("usuario"))]


def get_service(request: Request) -> ChatService:
    state = request.app.state
    agents: AgentsClient = state.agents_client
    clock: Clock = state.clock
    return ChatService(state.db_pool, agents, clock)


Service = Annotated[ChatService, Depends(get_service)]


def request_id(request: Request) -> str:
    """El identificador de la petición (ya validado por el middleware) viaja al agente como `X-Request-Id`."""
    return request_id_of(request) or uuid.uuid4().hex


def problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    texts = {
        401: "Sin sesión, o sesión inválida o caducada",
        403: "El rol de la cuenta no puede usar el asistente (solo `usuario`) o la cuenta está suspendida",
        404: "La conversación o el mensaje no existen (también si son de otra persona)",
        422: "Mensaje vacío (`message_empty`), de más de 2.000 caracteres (`message_too_long`) o datos no válidos",
        429: "Demasiados mensajes en la última hora (`chat_rate_limited`, con `Retry-After`)",
        503: "El asistente no responde (`agent_unavailable`, con `Retry-After`); el mensaje queda guardado y la respuesta lleva `conversation_id`",
    }
    return {status: {"model": ProblemDetails, "description": texts[status]} for status in statuses}


NO_STORE = {"Cache-Control": "private, no-store"}


@router.post(
    "/api/chat",
    operation_id="stream_chat",
    response_class=Response,
    summary="Enviar un mensaje al asistente y recibir su respuesta como flujo",
    responses={
        200: {
            "description": (
                "`text/event-stream`: `start`, `token`*, `citation`*, `tool_call`*, `abstention`?, `usage`? y `done` o `error`. "
                "Los eventos están descritos en la spec y en `frontend/src/lib/chat.ts`."
            )
        },
        **problems(401, 403, 404, 422, 429, 503),
    },
)
async def stream_chat(body: ChatBody, request: Request, user: Usuario, service: Service) -> Response:
    stream = await service.open_stream(user, request_id(request), body.conversation_id, body.content)
    return ChatStreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={**NO_STORE, "X-Accel-Buffering": "no"},  # sin acumular en ningún intermediario (nginx y similares)
    )


@router.get(
    "/api/chat/conversations",
    operation_id="list_chat_conversations",
    response_model=ConversationList,
    summary="Las conversaciones de la persona, por última actividad",
    responses=problems(401, 403),
)
def list_chat_conversations(response: Response, user: Usuario, service: Service) -> ConversationList:
    response.headers["Cache-Control"] = NO_STORE["Cache-Control"]
    return service.list_conversations(user)


@router.get(
    "/api/chat/conversations/{conversation_id}",
    operation_id="get_chat_conversation",
    response_model=ConversationDetail,
    summary="Una conversación con sus mensajes, citas y valoraciones",
    responses=problems(401, 403, 404),
)
def get_chat_conversation(
    conversation_id: UUID, response: Response, user: Usuario, service: Service
) -> ConversationDetail:
    response.headers["Cache-Control"] = NO_STORE["Cache-Control"]
    return service.get_conversation(user, conversation_id)


@router.delete(
    "/api/chat/conversations/{conversation_id}",
    operation_id="delete_chat_conversation",
    status_code=204,
    response_class=Response,
    summary="Borra la conversación con sus mensajes y valoraciones",
    responses=problems(401, 403, 404),
)
def delete_chat_conversation(conversation_id: UUID, user: Usuario, service: Service) -> Response:
    service.delete_conversation(user, conversation_id)
    return Response(status_code=204, headers=NO_STORE)


@router.put(
    "/api/chat/messages/{message_id}/feedback",
    operation_id="rate_chat_message",
    response_model=FeedbackOut,
    summary="Valora (o cambia la valoración de) una respuesta del asistente",
    responses=problems(401, 403, 404, 422),
)
def rate_chat_message(
    message_id: UUID, body: FeedbackBody, response: Response, user: Usuario, service: Service
) -> FeedbackOut:
    response.headers["Cache-Control"] = NO_STORE["Cache-Control"]
    return service.rate_message(user, message_id, body)
