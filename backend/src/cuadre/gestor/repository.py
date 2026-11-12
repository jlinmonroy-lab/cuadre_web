"""SQL del acceso del gestor (SQL explícito, sin ORM; ADR-0003). Toda escritura pasa por las funciones `app.*` de la base de datos.

Las funciones reciben una conexión que ya lleva la identidad de la persona (`user_transaction`). `translate_db_error` traduce los errores con código
estable de las funciones; lo que no se reconoce se propaga y la API lo responde como un 500 sin detalles.
"""

from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.errors import ProblemError, forbidden
from cuadre.gestor import errors

# `expired` se calcula: una invitación pendiente cuya fecha ya pasó. Es lo que ve el autónomo.
ACCESS_COLUMNS = (
    "id, gestor_email, CASE WHEN status = 'pending' AND expires_at < now() THEN 'expired' ELSE status::text END AS status, "
    "invited_at, expires_at"
)
LIST_LIMIT = 100

_PLAIN = {
    "invalid_email": errors.invalid_email,
    "cannot_invite_self": errors.cannot_invite_self,
    "gestor_access_already_open": errors.invitation_already_open,
    "too_many_open_invitations": errors.too_many_open_invitations,
    "gestor_access_not_found": errors.gestor_access_not_found,
    # Quien no es el dueño recibe «no encontrado»: no se revela que la invitación existe (como en la base de datos).
    "not_the_owner": errors.gestor_access_not_found,
    "gestor_access_not_open": errors.gestor_access_not_open,
    "gestor_access_not_pending": errors.gestor_access_not_pending,
    "gestor_access_expired": errors.gestor_access_expired,
}


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` -> problem+json. `None` si no es uno de ellos (se propaga: 500)."""
    if exc.sqlstate == "42501":
        return forbidden()
    if exc.sqlstate == "P0001":
        factory = _PLAIN.get(exc.diag.message_primary or "")
        return factory() if factory is not None else None
    return None


def invite(conn: Connection[DictRow], email: str) -> UUID:
    row = conn.execute("SELECT app.invite_gestor_access(%s) AS id", (email,)).fetchone()
    assert row is not None
    return row["id"]


def get_access(conn: Connection[DictRow], access_id: UUID) -> DictRow | None:
    return conn.execute(
        f"SELECT {ACCESS_COLUMNS} FROM public.gestor_access WHERE id = %s AND owner_id = (SELECT auth.uid())",
        (access_id,),
    ).fetchone()


def list_accesses(conn: Connection[DictRow]) -> list[DictRow]:
    """Los accesos de quien llama, el más reciente primero."""
    return conn.execute(
        f"SELECT {ACCESS_COLUMNS} FROM public.gestor_access WHERE owner_id = (SELECT auth.uid()) "
        "ORDER BY invited_at DESC, id LIMIT %s",
        (LIST_LIMIT,),
    ).fetchall()


def revoke(conn: Connection[DictRow], access_id: UUID) -> None:
    conn.execute("SELECT app.revoke_gestor_access(%s)", (access_id,))


def accept(conn: Connection[DictRow], access_id: UUID) -> None:
    conn.execute("SELECT app.accept_gestor_access(%s)", (access_id,))


def decline(conn: Connection[DictRow], access_id: UUID) -> None:
    conn.execute("SELECT app.decline_gestor_access(%s)", (access_id,))


def list_invitations(conn: Connection[DictRow]) -> list[DictRow]:
    return conn.execute("SELECT id, owner_name, invited_at, expires_at FROM app.list_gestor_invitations()").fetchall()
