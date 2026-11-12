"""Configuración de la aplicación, leída del entorno (y de .env en la raíz del repositorio).

La clave de servicio de Supabase y `DATABASE_SERVICE_URL` se declaran aquí pero solo se usan en `cuadre.jobs` y
`cuadre.cli` (SPEC-W-001, T-04); un test lo comprueba leyendo el código.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:3000"

    supabase_url: str
    # Rol cuadre_app: toda petición de usuario. La identidad se fija con SET LOCAL ROLE (ADR-0003).
    database_url: str

    # Servicio de agentes (ADR-0012). Sin URL: cliente simulado (nunca en production). Con URL: la clave es obligatoria.
    agents_base_url: str | None = None
    agents_api_key: SecretStr | None = None
    # Presupuesto total de una lectura, reintento incluido.
    agents_timeout_seconds: int = Field(default=45, ge=1, le=120)

    # Correo transaccional (ADR-0008). `console` escribe en consola (nunca en production: aún no hay proveedor real, DEP-05).
    email_provider: str = "console"

    # Solo cuadre.jobs y cuadre.cli.
    database_service_url: str | None = None
    supabase_service_role_key: SecretStr | None = None
    admin_password: SecretStr | None = None

    @field_validator("email_provider", mode="before")
    @classmethod
    def _email_provider_default(cls, value: object) -> object:
        """`EMAIL_PROVIDER=` vacío es «el de por defecto» (consola), y el valor se compara sin mayúsculas ni espacios."""
        if isinstance(value, str):
            return value.strip().lower() or "console"
        return value

    @field_validator("agents_base_url", "agents_api_key", mode="before")
    @classmethod
    def _blank_means_absent(cls, value: object) -> object:
        """`.env.example` trae `AGENTS_BASE_URL=` vacío: una cadena vacía es «sin servicio», no una URL vacía."""
        if isinstance(value, str):
            return value.strip() or None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # los campos obligatorios llegan del entorno
