"""Ámbito de un cliente (SPEC-W-006 D-01 y D-02): se **deduce** del país, nunca se escribe a mano.

También es el **único** sitio del mapeo al vocabulario del MCP (`nacional | ue | fuera_ue`, SPEC-W-011) y al de los gastos
(`public.supplier_scope`, `national | eu`, que no se toca).
"""

from cuadre.clients.countries import EU_COUNTRIES
from cuadre.clients.limits import SPAIN
from cuadre.clients.types import McpScope, Scope

_TO_MCP: dict[Scope, McpScope] = {"national": "nacional", "eu": "ue", "non_eu": "fuera_ue"}
_FROM_MCP: dict[str, Scope] = {mcp: scope for scope, mcp in _TO_MCP.items()}


def scope_of(country: str) -> Scope:
    """`national` si es España; `eu` si es otro Estado miembro; `non_eu` en cualquier otro caso. `country` ya viene normalizado."""
    if country == SPAIN:
        return "national"
    return "eu" if country in EU_COUNTRIES else "non_eu"


def to_mcp_scope(scope: Scope) -> McpScope:
    return _TO_MCP[scope]


def from_mcp_scope(name: object) -> Scope | None:
    """El ámbito de un nombre del MCP, o `None` si no es uno de los tres."""
    return _FROM_MCP.get(name) if isinstance(name, str) else None
