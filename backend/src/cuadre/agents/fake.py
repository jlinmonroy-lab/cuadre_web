"""Cliente simulado de agentes (ADR-0012, D-06). Sirve los fixtures de `contracts/examples/extract/` (C1) y `contracts/examples/chat/` (C2).

Se usa cuando no hay `AGENTS_BASE_URL` (nunca en producción: `get_agents_client`) y en los tests, donde se inyecta un guion exacto.
Los fixtures son los mismos que valida `contracts/tools/validate_examples.py`: web y agentes no pueden divergir. Los de chat se leen con el
**mismo lector SSE** que el cliente HTTP, así que cada uno ejercita la ruta real.
"""

import itertools
import re
from collections import deque
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from functools import cache

from cuadre.agents.client import check_user_token
from cuadre.agents.errors import AgentsConfigurationError, AgentsError, error_from_agent
from cuadre.agents.sse import frames_of
from cuadre.config import REPO_ROOT
from cuadre_contracts import ChatRequest, ChatStreamFrame, ExtractRequest, ExtractResponse
from cuadre_contracts.extract import AgentError, AgentErrorCode

FIXTURES_DIR = REPO_ROOT / "contracts" / "examples" / "extract"

# Orden fijo y cíclico (D-06). Cada nombre es `<nombre>.response.json`, o `<nombre>.error.json` si es un error del servicio.
DEFAULT_SEQUENCE = (
    "invoice_ok",
    "invoice_doubtful_nif",
    "invoice_sum_mismatch",
    "ticket_simplified",
    "invoice_injection",
    "unreadable",
)

# Estado HTTP con el que el servicio real responde cada error (contracts/agents-api/v1/openapi.yaml).
_STATUS_OF_ERROR = {
    AgentErrorCode.unreadable: 422,
    AgentErrorCode.unsupported_media_type: 415,
    AgentErrorCode.payload_too_large: 413,
    AgentErrorCode.invalid_request: 400,
    AgentErrorCode.unauthorized: 401,
    AgentErrorCode.upstream_error: 502,
}

ScriptItem = str | ExtractResponse | AgentsError  # nombre de fixture, respuesta ya construida o error a lanzar
MAX_RECORDED_CALLS = 50

CHAT_FIXTURES_DIR = REPO_ROOT / "contracts" / "examples" / "chat"

# Chat sin marcador: este orden, en bucle. Los errores (`CHAT_ERROR_FIXTURES`) solo salen si se piden con marcador o en un guion.
DEFAULT_CHAT_SEQUENCE = (
    "answer_with_citation",
    "abstention_professional",
    "answer_with_tool",
    "abstention_no_source",
    "abstention_out_of_scope",
    "answer_length",
)
CHAT_ERROR_FIXTURES = ("error_upstream", "error_tool")
CHAT_MARKER = re.compile(r"\[fixture:([a-z0-9_]+)\]")  # en el último mensaje: `[fixture:abstention_professional]`

ChatScriptItem = (
    str | AgentsError | Sequence[ChatStreamFrame]
)  # nombre de fixture, error a lanzar o frames ya construidos


@dataclass(frozen=True, slots=True)
class ChatCall:
    request: ChatRequest
    request_id: str
    had_user_token: bool  # el token en sí no se guarda


class FakeUnknownFixture(AssertionError):
    """Se pidió un fixture de chat que no existe (marcador `[fixture:…]` o guion con un nombre mal escrito): un fallo del test, no del agente."""


class FakeScriptExhausted(AssertionError):
    """El guion inyectado se acabó y alguien pidió otra lectura: en un test, casi siempre es un fallo (p. ej. una lectura doble)."""


@cache
def _load(name: str) -> ExtractResponse | AgentError:
    response_file = FIXTURES_DIR / f"{name}.response.json"
    error_file = FIXTURES_DIR / f"{name}.error.json"
    try:
        if response_file.exists():
            return ExtractResponse.model_validate_json(response_file.read_bytes(), strict=True)
        return AgentError.model_validate_json(error_file.read_bytes(), strict=True)
    except FileNotFoundError:
        raise AgentsConfigurationError(
            f"No se encuentra el fixture «{name}» en contracts/examples/extract/: el cliente simulado lo necesita."
        ) from None


@cache
def _load_chat(name: str) -> tuple[ChatStreamFrame, ...]:
    path = CHAT_FIXTURES_DIR / f"{name}.sse"
    try:
        return tuple(frames_of(path.read_bytes()))
    except FileNotFoundError:
        raise FakeUnknownFixture(f"No existe el fixture de chat «{name}» en contracts/examples/chat/.") from None


class FakeAgentsClient:
    """`script=None`: recorre `DEFAULT_SEQUENCE` en bucle. Con un guion, lo sirve en orden y falla si se agota.

    Chat: `[fixture:<nombre>]` en el último mensaje elige el ejemplo (y no gasta turno, así que varias pruebas en paralelo no se pisan);
    si no, `chat_script` en orden (y falla si se agota) o, sin él, `DEFAULT_CHAT_SEQUENCE` en bucle.
    """

    def __init__(
        self, script: Sequence[ScriptItem] | None = None, *, chat_script: Sequence[ChatScriptItem] | None = None
    ) -> None:
        self._script = None if script is None else tuple(script)
        self._turns = itertools.count()  # `next()` es atómico: varias peticiones a la vez no se pisan, sin cerrojo
        self.calls: deque[ExtractRequest] = deque(maxlen=MAX_RECORDED_CALLS)
        self._chat_script = None if chat_script is None else tuple(chat_script)
        self._chat_turns = itertools.count()
        self.chat_calls: deque[ChatCall] = deque(maxlen=MAX_RECORDED_CALLS)

    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        self.calls.append(request)
        turn = next(self._turns)
        if self._script is None:
            item: ScriptItem = DEFAULT_SEQUENCE[turn % len(DEFAULT_SEQUENCE)]
        elif turn < len(self._script):
            item = self._script[turn]
        else:
            raise FakeScriptExhausted(f"el guion tiene {len(self._script)} lecturas y se pidió la {turn + 1}")

        if isinstance(item, AgentsError):
            raise AgentsError(item.code, http_status=item.http_status, trace_id=item.trace_id)
        loaded = _load(item) if isinstance(item, str) else item
        if isinstance(loaded, AgentError):
            raise error_from_agent(_STATUS_OF_ERROR[loaded.code], loaded)
        return loaded.model_copy(deep=True)  # los fixtures se comparten: cada llamada recibe su copia

    async def stream_chat(
        self, request: ChatRequest, *, request_id: str, user_token: str | None = None
    ) -> AsyncIterator[ChatStreamFrame]:
        check_user_token(request, user_token)
        self.chat_calls.append(ChatCall(request, request_id, user_token is not None))
        item = self._next_chat_item(request)
        if isinstance(item, AgentsError):
            raise AgentsError(item.code, http_status=item.http_status, trace_id=item.trace_id)
        frames = _load_chat(item) if isinstance(item, str) else tuple(item)
        for frame in frames:
            yield frame.model_copy(deep=True)  # los fixtures se comparten: cada llamada recibe sus copias

    def _next_chat_item(self, request: ChatRequest) -> ChatScriptItem:
        marker = CHAT_MARKER.search(request.messages[-1].content)
        if marker is not None:
            return marker.group(1)
        turn = next(self._chat_turns)
        if self._chat_script is None:
            return DEFAULT_CHAT_SEQUENCE[turn % len(DEFAULT_CHAT_SEQUENCE)]
        if turn < len(self._chat_script):
            return self._chat_script[turn]
        raise FakeScriptExhausted(
            f"el guion de chat tiene {len(self._chat_script)} respuestas y se pidió la {turn + 1}"
        )
