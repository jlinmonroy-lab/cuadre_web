"""Configuración de la aplicación, leída del entorno (y de .env en la raíz del repositorio).

La clave de servicio de Supabase y `DATABASE_SERVICE_URL` se declaran aquí pero solo se usan en `cuadre.jobs` y
`cuadre.cli` (SPEC-W-001, T-04); un test lo comprueba leyendo el código.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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

    # Solo cuadre.jobs y cuadre.cli.
    database_service_url: str | None = None
    supabase_service_role_key: SecretStr | None = None
    admin_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # los campos obligatorios llegan del entorno
