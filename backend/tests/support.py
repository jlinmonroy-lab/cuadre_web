"""Utilidades compartidas por los tests de base de datos.

Los tests de RLS ejercitan el MISMO camino que la API: `cuadre.db.session.user_transaction`. Solo la preparación (crear usuarios
y estados) usa la conexión de administrador `TEST_DATABASE_ADMIN_URL`, que ningún código de la aplicación lee.
"""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import yaml
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.db import user_transaction

MATRIX_PATH = Path(__file__).parent / "rls" / "rls_matrix.yaml"

Pool = ConnectionPool[Connection[DictRow]]
KEYS = ("alicia", "beto", "gina", "gus", "adan")
ROLES = {"alicia": "usuario", "beto": "usuario", "gina": "gestor", "gus": "gestor", "adan": "admin"}


def load_matrix() -> dict[str, Any]:
    return yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Person:
    key: str
    id: uuid.UUID
    email: str

    @property
    def role(self) -> str:
        return ROLES[self.key]


@dataclass(frozen=True)
class Cast:
    """Reparto de cinco usuarios únicos por test: dos autónomos, dos gestores y un administrador."""

    alicia: Person
    beto: Person
    gina: Person
    gus: Person
    adan: Person

    def __getitem__(self, key: str) -> Person:
        return getattr(self, key)

    def everyone(self) -> list[Person]:
        return [self[k] for k in KEYS]

    def ids(self) -> set[uuid.UUID]:
        return {p.id for p in self.everyone()}


def create_user(admin: Connection[DictRow], key: str, suffix: str, *, metadata: dict[str, Any] | None = None) -> Person:
    """Inserta un usuario en auth.users (el trigger crea su perfil) y fija su rol."""
    user_id = uuid.uuid4()
    email = f"{key}.{suffix}@example.test"
    meta = {"display_name": key.capitalize(), **(metadata or {})}
    admin.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
                                raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                                confirmation_token, recovery_token, email_change_token_new, email_change)
        values (%s, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', %s, '', now(),
                '{"provider":"email","providers":["email"]}', %s, now(), now(), '', '', '', '')
        """,
        (user_id, email, json.dumps(meta)),
    )
    if ROLES[key] != "usuario":
        admin.execute("update public.profiles set role = %s where id = %s", (ROLES[key], user_id))
    return Person(key, user_id, email)


def make_cast(admin: Connection[DictRow]) -> Cast:
    suffix = uuid.uuid4().hex[:10]
    return Cast(**{key: create_user(admin, key, suffix) for key in KEYS})


@dataclass
class Outcome:
    rows: list[dict[str, Any]]
    rowcount: int
    sqlstate: str | None = None
    message: str | None = None

    @property
    def error(self) -> bool:
        return self.sqlstate is not None

    @property
    def blocked(self) -> bool:
        """La operación no hizo nada: falló o no afectó a ninguna fila."""
        return self.error or self.rowcount == 0


def attempt(pool: Pool, person: Person, sql: str, params: Any = None) -> Outcome:
    """Ejecuta `sql` como `person` en su propia transacción. Captura los errores de la base de datos."""
    try:
        with user_transaction(pool, person.id) as conn:
            cur = conn.execute(sql, params)
            rows = cur.fetchall() if cur.description else []
            return Outcome(rows, cur.rowcount)
    except psycopg.Error as exc:
        return Outcome([], 0, exc.sqlstate, str(exc).splitlines()[0])


def call(pool: Pool, person: Person, function: str, *args: Any) -> Outcome:
    """Invoca una función de `app.*` como `person`."""
    placeholders = ", ".join(["%s"] * len(args))
    return attempt(pool, person, f"select app.{function}({placeholders})", args)


def visible_owners(pool: Pool, person: Person, table: str, owner_column: str) -> set[uuid.UUID]:
    out = attempt(pool, person, f'select "{owner_column}" as owner from public."{table}"')
    assert not out.error, f"{person.key} no pudo leer {table}: {out.message}"
    return {row["owner"] for row in out.rows if row["owner"] is not None}


def invite(pool: Pool, owner: Person, gestor: Person) -> uuid.UUID:
    out = attempt(
        pool,
        owner,
        "insert into public.gestor_access (owner_id, gestor_email) values (%s, %s) returning id",
        (owner.id, gestor.email),
    )
    assert not out.error, out.message
    return out.rows[0]["id"]


def apply_scenario(pool: Pool, cast: Cast, scenario: str) -> uuid.UUID | None:
    """Lleva el vínculo Alicia → Gina a uno de los estados de la matriz. Devuelve el id de la invitación."""
    if scenario == "baseline":
        return None
    link_id = invite(pool, cast.alicia, cast.gina)
    if scenario == "pending":
        return link_id
    if scenario == "declined":
        out = call(pool, cast.gina, "decline_gestor_access", link_id)
        assert not out.error, out.message
        return link_id
    out = call(pool, cast.gina, "accept_gestor_access", link_id)
    assert not out.error, out.message
    if scenario == "revoked":
        out = call(pool, cast.alicia, "revoke_gestor_access", link_id)
        assert not out.error, out.message
    return link_id
