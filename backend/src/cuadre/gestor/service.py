"""Los flujos del acceso del gestor (SPEC-W-010 §5.3 y §5.4).

* **Invitar** abre una transacción corta, crea la invitación y la lee; el correo se envía **después del commit** y en la misma petición (ADR-0016: sin
  trabajo tras la respuesta). Si el envío falla, la invitación sigue pendiente y la respuesta lo dice (`email_sent: false`); nunca se registra la dirección.
* **Sin enumeración** (T10-04): se responde igual y se envía el mismo correo sea quien sea el destinatario; no se consulta si el correo es de una cuenta.
* **Nada de terceros en los registros** (T10-06): ni el correo del gestor ni el nombre de quien invita.
"""

import logging
from collections.abc import Callable
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.db import user_transaction
from cuadre.gestor import repository
from cuadre.gestor.models import GestorAccess, GestorInvitation, InvitedAccess
from cuadre.notifications import EmailDeliveryError, EmailSender, gestor_invitation

logger = logging.getLogger("cuadre.gestor")


class GestorService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], sender: EmailSender, app_url: str) -> None:
        self.pool = pool
        self.sender = sender
        self.app_url = app_url

    def _in_tx[T](self, user: CurrentUser, work: Callable[[Connection[DictRow]], T]) -> T:
        """Una transacción corta con la identidad de la persona. Los errores de las funciones `app.*` salen como problem+json."""
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                return work(conn)
        except psycopg.Error as exc:
            problem = repository.translate_db_error(exc)
            if problem is None:
                raise
            raise problem from None

    # --- Autónomo ---------------------------------------------------------------------------------------------------------------

    def invite(self, user: CurrentUser, email: str) -> InvitedAccess:
        def work(conn: Connection[DictRow]) -> DictRow:
            access_id = repository.invite(conn, email)
            row = repository.get_access(conn, access_id)
            assert row is not None
            return row

        row = self._in_tx(user, work)  # la transacción ya se confirmó: lo que sigue no puede deshacer la invitación
        sent = self._send_invitation(user, row["id"], row["gestor_email"])
        return InvitedAccess(**row, email_sent=sent)

    def _send_invitation(self, user: CurrentUser, access_id: UUID, to: str) -> bool:
        message = gestor_invitation(to=to, owner_name=user.display_name, app_url=self.app_url)
        try:
            self.sender.send(message)
        except EmailDeliveryError:
            logger.warning("gestor_invitation_email_failed", extra={"access_id": str(access_id)})
            return False
        return True

    def list_accesses(self, user: CurrentUser) -> list[GestorAccess]:
        return [GestorAccess(**row) for row in self._in_tx(user, repository.list_accesses)]

    def revoke(self, user: CurrentUser, access_id: UUID) -> None:
        self._in_tx(user, lambda conn: repository.revoke(conn, access_id))

    # --- Gestor -----------------------------------------------------------------------------------------------------------------

    def list_invitations(self, user: CurrentUser) -> list[GestorInvitation]:
        return [GestorInvitation(**row) for row in self._in_tx(user, repository.list_invitations)]

    def accept(self, user: CurrentUser, access_id: UUID) -> None:
        self._in_tx(user, lambda conn: repository.accept(conn, access_id))

    def decline(self, user: CurrentUser, access_id: UUID) -> None:
        self._in_tx(user, lambda conn: repository.decline(conn, access_id))
