"""Errores del cliente de agentes (SPEC-W-002 §5.1 «Motivos de fallo» y §5.4).

`FailureCode` es la lista cerrada de motivos con los que un documento queda en `extraction_failed`; coincide con la CHECK de
`documents.error_code` (un test lo comprueba). Ningún error lleva el cuerpo, el mensaje ni los datos que devolvió el agente:
son entrada no confiable (T2-05) y a veces contienen datos fiscales (NFR-11).
"""

from enum import StrEnum

from cuadre.agents.text import InvalidText, clean_text
from cuadre_contracts.extract import AgentError, AgentErrorCode

LIMIT_TRACE_ID = 200  # `documents.agent_trace_id` admite hasta 200 caracteres


class FailureCode(StrEnum):
    unreadable = "unreadable"
    unsupported_media_type = "unsupported_media_type"
    payload_too_large = "payload_too_large"
    timeout = "timeout"
    upstream_error = "upstream_error"
    agents_unavailable = "agents_unavailable"
    invalid_response = "invalid_response"
    internal = "internal"


class AgentsError(Exception):
    """La lectura no se pudo completar. `code` es lo único que se guarda y se enseña; `trace_id` ayuda a depurar con el otro equipo."""

    def __init__(self, code: FailureCode, *, http_status: int | None = None, trace_id: str | None = None) -> None:
        super().__init__(code.value)
        self.code = code
        self.http_status = http_status
        self.trace_id = trace_id


class AgentsConfigurationError(RuntimeError):
    """La configuración del cliente de agentes no es válida: la API no debe arrancar (D-06)."""


def error_from_agent(status: int, body: AgentError | None) -> AgentsError:
    """Traduce una respuesta de error del servicio de agentes (C1) a un motivo de fallo.

    Solo cuentan el estado HTTP y el `code` del cuerpo; el `message` del agente no se usa nunca.
    """
    try:
        trace_id = clean_text(body.trace_id, LIMIT_TRACE_ID) if body is not None else None
    except InvalidText:
        trace_id = None
    if status == 422 and body is not None and body.code == AgentErrorCode.unreadable:
        code = FailureCode.unreadable
    elif status == 413:
        code = FailureCode.payload_too_large
    elif status == 415:
        code = FailureCode.unsupported_media_type
    elif status in (400, 422):
        code = FailureCode.internal  # la petición que hemos enviado no es válida: un fallo nuestro, no del documento
    elif status == 429 or status >= 500:
        code = FailureCode.upstream_error
    else:  # 401, 403, 404, redirecciones y cualquier otro: credencial o URL mal configuradas
        code = FailureCode.agents_unavailable
    return AgentsError(code, http_status=status, trace_id=trace_id)
