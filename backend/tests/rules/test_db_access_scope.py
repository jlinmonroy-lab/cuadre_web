"""T-05 · Solo `cuadre.db` abre conexiones a la base de datos (ADR-0003).

Toda petición de usuario pasa por `user_transaction`; una conexión abierta por otro camino se saltaría `SET LOCAL ROLE` y las claims.
"""

import ast

from tests.rules.paths import SRC, python_files, rel

CONNECTION_FACTORIES = {"ConnectionPool", "AsyncConnectionPool", "create_engine", "create_async_engine"}
DRIVERS = {"psycopg", "asyncpg", "psycopg2", "sqlalchemy", "Connection", "AsyncConnection"}


def opens_connection(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in CONNECTION_FACTORIES | {"connect"}:
            found.append(f"línea {node.lineno}: {func.id}(...)")
        elif isinstance(func, ast.Attribute):
            owner = func.value.id if isinstance(func.value, ast.Name) else None
            if func.attr in CONNECTION_FACTORIES or (func.attr == "connect" and owner in DRIVERS):
                found.append(f"línea {node.lineno}: {owner or '?'}.{func.attr}(...)")
    return found


def test_the_detector_flags_connections() -> None:
    assert opens_connection("import psycopg\nc = psycopg.connect('x')")
    assert opens_connection("from psycopg_pool import ConnectionPool\np = ConnectionPool('x')")
    assert opens_connection("from psycopg import connect\nconnect('x')")
    assert opens_connection("e = create_engine('x')")
    assert opens_connection("conn.execute('select 1')\nnonlocal_call()") == []


def test_only_the_db_package_opens_connections() -> None:
    offenders = {}
    for path in python_files(SRC):
        if path.relative_to(SRC).parts[0] == "db":
            continue
        if hits := opens_connection(path.read_text(encoding="utf-8")):
            offenders[rel(path)] = hits
    assert offenders == {}


def test_the_api_package_does_not_use_the_service_role() -> None:
    for path in python_files(SRC / "api", SRC / "core"):
        assert "service_transaction" not in path.read_text(encoding="utf-8"), rel(path)
