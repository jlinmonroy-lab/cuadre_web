"""Cliente simulado de agentes (ADR-0012, D-06). Sirve los fixtures de `contracts/examples/extract/`.

Se usa cuando no hay `AGENTS_BASE_URL` (nunca en producción: `get_agents_client`) y en los tests, donde se inyecta un guion exacto.
Los fixtures son los mismos que valida `contracts/tools/validate_examples.py`: web y agentes no pueden divergir.
"""

import itertools
from collections import deque
from collections.abc import Sequence
from functools import cache

from cuadre.agents.errors import AgentsConfigurationError, AgentsError, error_from_agent
from cuadre.config import REPO_ROOT
from cuadre_contracts import ExtractRequest, ExtractResponse
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


class FakeAgentsClient:
    """`script=None`: recorre `DEFAULT_SEQUENCE` en bucle. Con un guion, lo sirve en orden y falla si se agota."""

    def __init__(self, script: Sequence[ScriptItem] | None = None) -> None:
        self._script = None if script is None else tuple(script)
        self._turns = itertools.count()  # `next()` es atómico: varias peticiones a la vez no se pisan, sin cerrojo
        self.calls: deque[ExtractRequest] = deque(maxlen=MAX_RECORDED_CALLS)

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
