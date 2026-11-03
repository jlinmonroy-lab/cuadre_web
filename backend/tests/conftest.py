"""Fixtures comunes. Los tests de base de datos necesitan la pila local de Supabase:

npx supabase start && npx supabase db reset
"""

import os
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

# Valores de la pila local. Se aplican antes de importar la configuración y NO pisan variables ya definidas (CI).
os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:54321")
os.environ.setdefault("DATABASE_URL", "postgresql://cuadre_app:cuadre-dev-only@127.0.0.1:54322/postgres")
os.environ.setdefault("DATABASE_SERVICE_URL", "postgresql://cuadre_jobs:cuadre-dev-only@127.0.0.1:54322/postgres")
os.environ.setdefault("TEST_DATABASE_ADMIN_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")

from cuadre.db import open_pool  # noqa: E402
from tests.support import Cast, Pool, make_cast  # noqa: E402


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Todo lo que cuelga de tests/rls lleva el marcador `rls` (puerta NFR-06) sin repetirlo en cada prueba."""
    for item in items:
        if "/rls/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.rls)


@pytest.fixture(scope="session")
def admin() -> Iterator[Connection[DictRow]]:
    """Conexión como `postgres` (BYPASSRLS), en autocommit. SOLO para preparar y comprobar estado en los tests."""
    try:
        conn = psycopg.connect(os.environ["TEST_DATABASE_ADMIN_URL"], autocommit=True, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        pytest.exit(f"No se puede conectar a la base de datos local ({exc}). ¿Está en marcha `npx supabase start`?", 2)
    with conn:
        yield conn


@pytest.fixture(scope="session")
def app_pool() -> Iterator[Pool]:
    pool = open_pool(os.environ["DATABASE_URL"], name="tests-app", max_size=4)
    yield pool
    pool.close()


@pytest.fixture(scope="session")
def service_pool() -> Iterator[Pool]:
    pool = open_pool(os.environ["DATABASE_SERVICE_URL"], name="tests-service", max_size=2)
    yield pool
    pool.close()


@pytest.fixture
def cast(admin: Connection[DictRow]) -> Cast:
    """Cinco usuarios nuevos por test: ninguno depende del estado que dejó otro."""
    return make_cast(admin)
