"""Dominio de los clientes (SPEC-W-006, RF-005): Python puro, sin base de datos, sin red y sin reloj propio.

La API lo usa para validar la ficha de un cliente, deducir su ámbito y calcular el estado simulado de VIES. El NIF y el NIF-IVA los normaliza
`cuadre.validators` (la única puerta a `python-stdnum`); aquí no se importa `stdnum`.
"""

from cuadre.clients.countries import COUNTRIES, EU_COUNTRIES
from cuadre.clients.rules import MESSAGES, tax_id_rule, validate_client, vat_prefix
from cuadre.clients.scope import from_mcp_scope, scope_of, to_mcp_scope
from cuadre.clients.types import ClientResult, ClientValues, FieldError, Kind, McpScope, RawClient, Scope, ViesStatus
from cuadre.clients.vies import FakeViesChecker, ViesChecker

__all__ = [
    "COUNTRIES",
    "EU_COUNTRIES",
    "MESSAGES",
    "ClientResult",
    "ClientValues",
    "FakeViesChecker",
    "FieldError",
    "Kind",
    "McpScope",
    "RawClient",
    "Scope",
    "ViesChecker",
    "ViesStatus",
    "from_mcp_scope",
    "scope_of",
    "tax_id_rule",
    "to_mcp_scope",
    "validate_client",
    "vat_prefix",
]
