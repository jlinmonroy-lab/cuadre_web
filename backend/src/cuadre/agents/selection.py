"""Qué cliente de agentes usa la aplicación según el entorno (ADR-0012, D-06, SPEC-W-002 §5.4).

| `AGENTS_BASE_URL` | `APP_ENV`                 | Resultado                                                                       |
|-------------------|---------------------------|---------------------------------------------------------------------------------|
| ausente           | `local`                   | `FakeAgentsClient`                                                              |
| ausente           | `staging`                 | `FakeAgentsClient`, con un aviso en el registro                                 |
| ausente           | `production`              | la API no arranca: nunca un simulacro silencioso en producción                  |
| presente          | cualquiera                | `HttpAgentsClient`; exige `AGENTS_API_KEY`, y `https` salvo en `local`          |

Los mensajes de error nombran la variable, nunca su valor (la URL podría llevar credenciales).
"""

import logging
from urllib.parse import urlsplit

from cuadre.agents.client import AgentsClient
from cuadre.agents.errors import AgentsConfigurationError
from cuadre.agents.fake import FakeAgentsClient
from cuadre.agents.http import HttpAgentsClient
from cuadre.config import Settings

logger = logging.getLogger("cuadre.agents")


def get_agents_client(settings: Settings) -> AgentsClient:
    base_url = settings.agents_base_url
    if base_url is None:
        if settings.app_env == "production":
            raise AgentsConfigurationError(
                "Con APP_ENV=production, AGENTS_BASE_URL es obligatoria: no se usa el cliente simulado en producción."
            )
        if settings.app_env != "local":
            logger.warning("agents_fake_in_use", extra={"app_env": settings.app_env})
        return FakeAgentsClient()

    if settings.agents_api_key is None:
        raise AgentsConfigurationError("AGENTS_API_KEY es obligatoria cuando hay AGENTS_BASE_URL.")
    return HttpAgentsClient(
        _checked_base_url(base_url, allow_plain_http=settings.app_env == "local"),
        settings.agents_api_key.get_secret_value(),
        timeout_ms=settings.agents_timeout_seconds * 1000,
    )


def _checked_base_url(value: str, *, allow_plain_http: bool) -> str:
    try:
        parts = urlsplit(value)
        port = parts.port  # lanza ValueError si no es un número válido
    except ValueError:
        raise AgentsConfigurationError("AGENTS_BASE_URL no es una URL válida.") from None
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise AgentsConfigurationError("AGENTS_BASE_URL debe ser una URL http(s) con host.")
    if parts.scheme == "http" and not allow_plain_http:
        raise AgentsConfigurationError("AGENTS_BASE_URL debe usar https (http solo se admite con APP_ENV=local).")
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        raise AgentsConfigurationError("AGENTS_BASE_URL no puede llevar usuario, contraseña, consulta ni fragmento.")
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname  # IPv6 literal
    return f"{parts.scheme}://{host}{f':{port}' if port is not None else ''}{parts.path.rstrip('/')}"
