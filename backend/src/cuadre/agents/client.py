"""Interfaz del cliente de agentes (ADR-0012, SPEC-W-002 §5.4, SPEC-W-004 §5.4).

Este repositorio no llama a ningún modelo de lenguaje: todo lo que necesita IA pasa por un `AgentsClient`. Añadir un método al Protocol no
rompe a quien ya lo implementa mientras no lo use.
"""

from collections.abc import AsyncIterator
from typing import Protocol

from cuadre_contracts import ChatRequest, ChatStreamFrame, ExtractRequest, ExtractResponse


class AgentsClient(Protocol):
    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        """Lee un documento. Lanza `AgentsError` ante cualquier fallo; nunca devuelve datos a medias.

        La respuesta es entrada no confiable: quien la recibe la pasa por `normalize_extraction` antes de guardar nada.
        """
        ...

    def stream_chat(
        self, request: ChatRequest, *, request_id: str, user_token: str | None = None
    ) -> AsyncIterator[ChatStreamFrame]:
        """Responde en el chat (C2). Un generador asíncrono de los frames del contrato, en el orden en que llegan.

        - **`user_token`** (token MCP derivado, ADR-0013): se envía si y solo si `request.mcp_url` no es `None`; la combinación contraria es un
          error de programación y lanza `ValueError`. Nunca se registra.
        - **Lo que entrega:** solo frames válidos del contrato. Los eventos desconocidos se descartan. Termina tras el primer `done` o `error`
          (el `error` del propio agente se entrega como un frame y no lanza nada); lo que viniera después se ignora.
        - **Fallos:** `AgentsError` (antes o después del primer frame; el que llama sabe si ya emitió algo). El orden de los frames lo
          comprueba `cuadre.chat.rules`, no el cliente.
        - **Cancelación:** cerrar el generador (`aclose()`) o cancelarlo cierra la conexión con el agente.
        """
        ...


def check_user_token(request: ChatRequest, user_token: str | None) -> None:
    """`X-User-Token` va si y solo si hay herramientas (`mcp_url`): contrato C2 1.1.0. Un descuido aquí se vería como un fallo del agente."""
    if (request.mcp_url is None) != (user_token is None):
        raise ValueError("`user_token` debe darse si y solo si la petición lleva `mcp_url`.")
