"""SQL de clientes (SQL explícito, sin ORM; ADR-0003). Toda escritura pasa por las funciones `app.*` del hito 2.

Las funciones reciben una conexión que ya lleva la identidad de la persona (`user_transaction`). `translate_db_error` traduce los errores con
código estable de §5.2 («Para el hito 3» del Anexo B.3); lo que no se reconoce se propaga y la API lo responde como un 500 sin detalles: son
errores de construcción (`invalid_client`, que la API ya validó con el dominio), de trigger o de base que la validación previa debería haber
impedido.
"""

from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.clients import errors
from cuadre.clients.types import ClientValues
from cuadre.core.errors import ProblemError, forbidden

COLUMNS = (
    "id, name, kind::text AS kind, country, scope::text AS scope, tax_id, address, vies_status::text AS vies_status, "
    "(archived_at IS NOT NULL) AS archived, created_at, updated_at"
)

_PLAIN = {
    "client_not_found": errors.client_not_found,
    "client_archived": errors.client_archived,
    "client_tax_id_taken": errors.client_tax_id_taken,
}
_UNIQUE = {"clients_owner_tax_id_active": errors.client_tax_id_taken}


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` -> problem+json. `None` si no es uno de ellos (se propaga: 500)."""
    if exc.sqlstate == "42501":
        return forbidden()
    if exc.sqlstate == "P0001":
        factory = _PLAIN.get(exc.diag.message_primary or "")
        return factory() if factory is not None else None
    if exc.sqlstate == "23505":
        factory = _UNIQUE.get(exc.diag.constraint_name or "")
        return factory() if factory is not None else None
    return None


# --- Lectura ---------------------------------------------------------------------------------------------------------------------


def list_clients(conn: Connection[DictRow], include_archived: bool) -> list[DictRow]:
    """Los clientes de quien llama, por nombre en el orden del español (la ñ después de la n; Anexo B.1-C)."""
    return conn.execute(
        f"SELECT {COLUMNS} FROM public.clients WHERE owner_id = (SELECT private.read_owner()) AND (%(all)s OR archived_at IS NULL) "
        'ORDER BY name COLLATE "es-x-icu", id',
        {"all": include_archived},
    ).fetchall()


def get_client(conn: Connection[DictRow], client_id: UUID) -> DictRow | None:
    return conn.execute(
        f"SELECT {COLUMNS} FROM public.clients WHERE id = %s AND owner_id = (SELECT auth.uid())", (client_id,)
    ).fetchone()


# --- Escritura (solo funciones app.*) ----------------------------------------------------------------------------------------------


def _fields(values: ClientValues) -> tuple[object, ...]:
    return (values.name, values.kind, values.country, values.scope, values.tax_id, values.address, values.vies_status)


def create_client(conn: Connection[DictRow], values: ClientValues) -> UUID:
    row = conn.execute("SELECT app.create_client(%s, %s, %s, %s, %s, %s, %s) AS id", _fields(values)).fetchone()
    assert row is not None
    return row["id"]


def update_client(conn: Connection[DictRow], client_id: UUID, values: ClientValues) -> None:
    conn.execute("SELECT app.update_client(%s, %s, %s, %s, %s, %s, %s, %s)", (client_id, *_fields(values)))


def set_archived(conn: Connection[DictRow], client_id: UUID, archived: bool) -> None:
    conn.execute("SELECT app.set_client_archived(%s, %s)", (client_id, archived))
