"""Modelos Pydantic de los contratos web <-> agentes de Cuadre (fuente de los esquemas JSON)."""

from .chat import ChatRequest, ChatStreamFrame
from .extract import AgentError, ExtractedInvoice, ExtractRequest, ExtractResponse
from .mcp_tools import TOOLS, ToolError

__all__ = [
    "TOOLS",
    "AgentError",
    "ChatRequest",
    "ChatStreamFrame",
    "ExtractRequest",
    "ExtractResponse",
    "ExtractedInvoice",
    "ToolError",
]
