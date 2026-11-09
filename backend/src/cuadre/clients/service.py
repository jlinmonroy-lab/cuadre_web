"""Los flujos de clientes (SPEC-W-006 §5.3 y §5.4).

* **Una lectura no escribe** (T6-05): `list_clients` y `get_client` solo leen.
* **Todo o nada** (§5.1): se valida todo con `cuadre.clients` ANTES de tocar la base; si algo falla, no se guarda nada y se devuelven todos los
  errores. El ámbito, la clave del NIF y el estado de VIES los calcula el dominio: nunca vienen de quien llama.
* **Nada de terceros en los registros** (T6-04): ni nombre, ni NIF, ni domicilio de un cliente. Los mensajes dicen el campo, no el valor.
"""

from collections.abc import Callable
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.clients import errors, repository
from cuadre.clients.models import Client, ClientInput
from cuadre.clients.rules import validate_client
from cuadre.clients.types import ClientValues, RawClient
from cuadre.clients.vies import ViesChecker
from cuadre.core.auth import CurrentUser
from cuadre.db import user_transaction


class ClientService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], checker: ViesChecker) -> None:
        self.pool = pool
        self.checker = checker

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

    def _validated(self, body: ClientInput) -> ClientValues:
        result = validate_client(RawClient(body.name, body.kind, body.country, body.tax_id, body.address), self.checker)
        if result.values is None:
            raise errors.invalid_client(result.errors)
        return result.values

    @staticmethod
    def _client(conn: Connection[DictRow], client_id: UUID) -> Client:
        row = repository.get_client(conn, client_id)
        if row is None:
            raise errors.client_not_found()
        return Client(**row)

    # --- Lecturas -------------------------------------------------------------------------------------------------------

    def list_clients(self, user: CurrentUser, include_archived: bool) -> list[Client]:
        return [
            Client(**row) for row in self._in_tx(user, lambda conn: repository.list_clients(conn, include_archived))
        ]

    def get_client(self, user: CurrentUser, client_id: UUID) -> Client:
        return self._in_tx(user, lambda conn: self._client(conn, client_id))

    # --- Escrituras -----------------------------------------------------------------------------------------------------

    def create_client(self, user: CurrentUser, body: ClientInput) -> Client:
        values = self._validated(body)

        def work(conn: Connection[DictRow]) -> Client:
            return self._client(conn, repository.create_client(conn, values))

        return self._in_tx(user, work)

    def update_client(self, user: CurrentUser, client_id: UUID, body: ClientInput) -> Client:
        values = self._validated(body)

        def work(conn: Connection[DictRow]) -> Client:
            repository.update_client(conn, client_id, values)
            return self._client(conn, client_id)

        return self._in_tx(user, work)

    def set_client_archived(self, user: CurrentUser, client_id: UUID, archived: bool) -> Client:
        def work(conn: Connection[DictRow]) -> Client:
            repository.set_archived(conn, client_id, archived)
            return self._client(conn, client_id)

        return self._in_tx(user, work)
