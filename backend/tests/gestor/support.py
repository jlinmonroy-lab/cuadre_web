"""Ayudas de las pruebas de lectura del gestor (SPEC-W-010 hito 2): vincular, dejar pendientes, un Storage de mentira y atajos de consulta."""

import uuid
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Doc, Person, Pool, advance, call, invite, new_document


def link(pool: Pool, owner: Person, gestor: Person) -> uuid.UUID:
    """Un vínculo ACTIVO owner → gestor (invitar y aceptar, como en la aplicación)."""
    link_id = invite(pool, owner, gestor)
    out = call(pool, gestor, "accept_gestor_access", link_id)
    assert not out.error, out.message
    return link_id


def documents(pool: Pool, person: Person, state: str, count: int = 1) -> list[Doc]:
    """`count` documentos de `person` en el estado pedido (`review`, `processing`, `extraction_failed`…)."""
    return [advance(pool, person, new_document(pool, person, filename=f"doc-{k}.pdf"), state) for k in range(count)]


class FakeStorage:
    """Un Storage que solo firma lecturas: apunta lo que se le pide (ruta, JWT y vida) y devuelve una URL reconocible. No hay red."""

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.signed: list[tuple[str, str, int]] = []
        self.fail = fail

    def sign_read(self, path: str, *, token: str, expires_in: int) -> str:
        if self.fail is not None:
            raise self.fail
        self.signed.append((path, token, expires_in))
        return f"https://storage.example.test/{path}?sig=fake"


def access_log(admin: Connection[DictRow], owner: Person) -> list[dict[str, Any]]:
    """Lo que hay en `activity_log` de esa cuenta, en orden, tal como lo ve la base (con privilegios de administrador)."""
    return admin.execute(
        "select id, action, actor_id, actor_role::text as actor_role, category::text as category, entity_type, entity_id, metadata "
        "from public.activity_log where owner_id = %s order by id",
        (owner.id,),
    ).fetchall()


def reads(admin: Connection[DictRow], owner: Person) -> list[dict[str, Any]]:
    return [row for row in access_log(admin, owner) if row["action"] == "gestor.read"]


def invoice_body(response: Any) -> Any:
    assert response.status_code == 200, response.text
    return response.json()
