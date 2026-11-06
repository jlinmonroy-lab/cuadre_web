"""Cliente de agentes (ADR-0012): la única puerta de este repositorio hacia cuadre-agents.

`AgentsClient` es la interfaz; `FakeAgentsClient` y `HttpAgentsClient` las implementaciones; `normalize_extraction` es lo único que
deja pasar una lectura hacia la base de datos; `get_agents_client(settings)` elige según el entorno.
"""

from cuadre.agents.client import AgentsClient
from cuadre.agents.errors import AgentsConfigurationError, AgentsError, FailureCode
from cuadre.agents.fake import FakeAgentsClient
from cuadre.agents.http import HttpAgentsClient
from cuadre.agents.normalize import NormalizedReading, normalize_extraction
from cuadre.agents.selection import get_agents_client

__all__ = [
    "AgentsClient",
    "AgentsConfigurationError",
    "AgentsError",
    "FailureCode",
    "FakeAgentsClient",
    "HttpAgentsClient",
    "NormalizedReading",
    "get_agents_client",
    "normalize_extraction",
]
