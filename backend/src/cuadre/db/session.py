"""Acceso a PostgreSQL con la identidad del usuario (ADR-0003, ADR-0015).

Este es el ÚNICO módulo de `cuadre` que abre conexiones (SPEC-W-001, T-05). Cada petición de usuario se ejecuta en una
transacción que empieza con `SET LOCAL ROLE authenticated` y las claims del JWT en `request.jwt.claims`, de modo que
`auth.uid()` y las políticas RLS se comportan exactamente igual que con PostgREST.

Detalles que importan:

* `SET LOCAL` solo vive hasta el final de la transacción. `pool.connection()` hace commit o rollback al salir, así
  que el rol nunca se filtra a la petición siguiente que reutilice la conexión
  (`test_role_does_not_leak_to_the_next_request`).
* No usar `conn.transaction()` dentro de `user_transaction` esperando una transacción nueva: la conexión ya tiene una
  abierta y psycopg crearía un *savepoint*; `SET LOCAL` seguiría vivo hasta el final de la transacción externa.
* `prepare_threshold=None`: compatible con el pooler de Supabase en modo transacción.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool


def open_pool(dsn: str, *, name: str, min_size: int = 1, max_size: int = 10) -> ConnectionPool[Connection[DictRow]]:
    """Abre un pool de conexiones síncronas que devuelven filas como diccionarios."""
    pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
        dsn,
        name=name,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
        open=False,
    )
    pool.open(wait=True, timeout=15)
    return pool


@contextmanager
def user_transaction(
    pool: ConnectionPool[Connection[DictRow]],
    user_id: UUID | str,
    claims: dict[str, Any] | None = None,
) -> Iterator[Connection[DictRow]]:
    """Transacción con la identidad de `user_id`: rol `authenticated` y claims fijadas.

    Hace commit al salir y rollback si se propaga una excepción.
    """
    subject = str(UUID(str(user_id)))  # valida el formato antes de que llegue a la base de datos
    payload = {"aud": "authenticated", **(claims or {}), "role": "authenticated", "sub": subject}
    with pool.connection() as conn:
        conn.execute("SET LOCAL ROLE authenticated")
        conn.execute(
            "SELECT set_config('request.jwt.claims', %s, true), set_config('request.jwt.claim.sub', %s, true)",
            (json.dumps(payload), subject),
        )
        yield conn


@contextmanager
def service_transaction(pool: ConnectionPool[Connection[DictRow]]) -> Iterator[Connection[DictRow]]:
    """Transacción como `service_role`. Solo para `cuadre.jobs` y `cuadre.cli` (T-04).

    El pool debe abrirse con `DATABASE_SERVICE_URL` (rol `cuadre_jobs`, que no tiene privilegios propios): si un job
    olvidara cambiar de rol, fallaría con «permission denied» en vez de saltarse la RLS.
    """
    with pool.connection() as conn:
        conn.execute("SET LOCAL ROLE service_role")
        yield conn
