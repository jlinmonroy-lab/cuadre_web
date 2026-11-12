"""`owner_scope`: leer lo de un autónomo como gestor, con el vínculo comprobado y la lectura registrada EN LA MISMA TRANSACCIÓN (SPEC-W-010 D-05 y D-06).

El orden importa y no se puede alterar:

1. `app.log_gestor_read` exige el rol `gestor` y el vínculo activo con ese autónomo (si no, `42501`) y escribe `gestor.read` en `activity_log`. Si falla, **no se
   devuelve ningún dato**: la excepción aborta la transacción antes de leer nada.
2. Solo entonces se fija `cuadre.read_owner` (local a la transacción) para que las MISMAS consultas del autónomo (`private.read_owner()`) miren a ese dueño. No
   concede nada: la RLS sigue decidiendo qué filas ve el gestor.
3. Se lee con `work(conn)`.

El `42501` se traduce a un `404` uniforme (`not_found`): igual sin vínculo, con vínculo revocado o caducado, de otro gestor y para un id que no existe, así que no
se averigua qué ids son autónomos (T10-04). Nada de lo que se escribe aquí lleva importes, nombres, NIF, IBAN, conceptos ni URLs firmadas (T10-06).
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.db import user_transaction
from cuadre.gestor import errors


def begin(
    conn: Connection[DictRow],
    owner: UUID,
    entity_type: str,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Comprueba el vínculo, registra la lectura y fija de quién es lo que se va a leer. Lanza el `404` uniforme si no hay vínculo."""
    try:
        conn.execute(
            "SELECT app.log_gestor_read(%s, %s, %s, %s)",
            (owner, entity_type, entity_id, Jsonb(metadata) if metadata else None),
        )
    except psycopg.errors.InsufficientPrivilege:
        raise errors.not_found() from None
    conn.execute("SELECT set_config('cuadre.read_owner', %s, true)", (str(owner),))


def read_as_gestor[T](
    pool: ConnectionPool[Connection[DictRow]],
    gestor: CurrentUser,
    owner: UUID,
    entity_type: str,
    work: Callable[[Connection[DictRow]], T],
    *,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> T:
    """Una transacción con la identidad del gestor: vínculo y registro primero, la lectura después."""
    with user_transaction(pool, gestor.id, gestor.claims) as conn:
        begin(conn, owner, entity_type, entity_id, metadata)
        return work(conn)
