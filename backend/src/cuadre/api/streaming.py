"""La respuesta en streaming del chat (SPEC-W-004 §5.4, D-07).

`StreamingResponse` de Starlette, cuando el navegador corta (con uvicorn, `http.disconnect` y `spec_version` 2.3), cancela la tarea que envía el cuerpo. Si
el generador está suspendido en un `yield` en ese momento, la cancelación salta en `stream_response` y **nadie llama a `aclose()` del generador**: su
`finally` (donde se guarda el mensaje `interrupted` y se cierra la conexión con el agente) quedaría a merced del finalizador del bucle, sin orden
garantizado y, en una función de Vercel que se congela, quizá nunca. Esta subclase lo cierra siempre, bajo escudo de cancelación.
"""

import anyio
from starlette.responses import StreamingResponse
from starlette.types import Send


class ChatStreamingResponse(StreamingResponse):
    async def stream_response(self, send: Send) -> None:
        try:
            await super().stream_response(send)
        finally:
            close = getattr(self.body_iterator, "aclose", None)
            if close is not None:
                with anyio.CancelScope(shield=True):
                    await close()
