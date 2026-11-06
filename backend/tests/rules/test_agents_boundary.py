"""ADR-0012, T2-03, AC-08 · `cuadre.agents` es la frontera con cuadre-agents y estructuralmente no puede cruzar nada más.

No importa la base de datos, ni la autenticación, ni el JWT de la persona, ni la API; y de la configuración solo lee lo suyo
(`AGENTS_*` y `APP_ENV`). Así «nunca envía la service key ni el JWT de la persona» no depende de que alguien se acuerde.
"""

import ast

from tests.rules.paths import SRC, python_files, rel

AGENTS = SRC / "agents"
FORBIDDEN_IMPORTS = ("cuadre.db", "cuadre.core", "cuadre.api", "psycopg", "psycopg_pool", "jwt", "supabase")
ALLOWED_SETTINGS = {"agents_base_url", "agents_api_key", "agents_timeout_seconds", "app_env"}


def forbidden_imports(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        modules = []
        if isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        found += [m for m in modules if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS)]
    return found


def settings_attributes_outside_agents_scope(source: str) -> list[str]:
    return [
        f"settings.{node.attr}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "settings"
        and node.attr not in ALLOWED_SETTINGS
    ]


def test_the_detectors_detect() -> None:
    assert forbidden_imports("from cuadre.db import user_transaction")
    assert forbidden_imports("import psycopg")
    assert forbidden_imports("from cuadre.core.auth import get_claims")
    assert forbidden_imports("import jwt")
    assert forbidden_imports("from cuadre.config import Settings\nfrom cuadre.agents.errors import AgentsError") == []
    assert settings_attributes_outside_agents_scope("x = settings.supabase_service_role_key")
    assert settings_attributes_outside_agents_scope("x = settings.supabase_url")
    assert settings_attributes_outside_agents_scope("x = settings.agents_api_key; y = settings.app_env") == []


def test_the_agents_package_exists_and_has_code() -> None:
    assert len(list(python_files(AGENTS))) >= 6


def test_the_agents_package_imports_nothing_that_reaches_the_database_or_the_users_identity() -> None:
    offenders = {
        rel(p): hits for p in python_files(AGENTS) if (hits := forbidden_imports(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_agents_package_reads_only_its_own_settings() -> None:
    offenders = {
        rel(p): hits
        for p in python_files(AGENTS)
        if (hits := settings_attributes_outside_agents_scope(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}
