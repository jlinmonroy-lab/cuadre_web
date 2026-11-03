"""AC-01 (parte de base de datos) · El alta de un usuario crea su perfil, su ficha de negocio vacía y su registro."""

import json
import uuid

from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import create_user


def row(admin: Connection[DictRow], sql: str, params: tuple) -> dict:
    found = admin.execute(sql, params).fetchone()
    assert found is not None
    return found


def test_signup_creates_profile_business_profile_and_log(admin: Connection[DictRow]) -> None:
    person = create_user(admin, "alicia", uuid.uuid4().hex[:10])

    profile = row(admin, "select * from public.profiles where id = %s", (person.id,))
    assert profile["role"] == "usuario"
    assert profile["status"] == "active"
    assert profile["email"] == person.email
    assert profile["display_name"] == "Alicia"

    business = row(admin, "select * from public.business_profiles where owner_id = %s", (person.id,))
    assert business["vat_regime"] == "general"
    empty = (
        "legal_name",
        "tax_id",
        "fiscal_address",
        "activity",
        "iae_epigraph",
        "iban",
        "logo_path",
        "irpf_rate",
        "home_pct",
    )
    assert all(business[column] is None for column in empty)

    log = row(
        admin,
        "select * from public.activity_log where owner_id = %s and action = 'account.created'",
        (person.id,),
    )
    assert log["category"] == "account"
    assert log["actor_id"] is None


def test_a_role_in_the_signup_metadata_is_ignored(admin: Connection[DictRow]) -> None:
    person = create_user(admin, "beto", uuid.uuid4().hex[:10], metadata={"role": "admin", "status": "suspended"})
    profile = row(admin, "select role, status from public.profiles where id = %s", (person.id,))
    assert (profile["role"], profile["status"]) == ("usuario", "active")


def test_the_profile_email_is_lowercase(admin: Connection[DictRow]) -> None:
    user_id = uuid.uuid4()
    mixed = f"Mixed.{uuid.uuid4().hex[:8]}@Example.TEST"
    admin.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
                                raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                                confirmation_token, recovery_token, email_change_token_new, email_change)
        values (%s, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', %s, '', now(),
                '{}', %s, now(), now(), '', '', '', '')
        """,
        (user_id, mixed, json.dumps({})),
    )
    assert row(admin, "select email from public.profiles where id = %s", (user_id,))["email"] == mixed.lower()


def test_changing_the_auth_email_updates_the_profile(admin: Connection[DictRow]) -> None:
    person = create_user(admin, "gina", uuid.uuid4().hex[:10])
    new_email = f"nuevo.{uuid.uuid4().hex[:8]}@example.test"
    admin.execute("update auth.users set email = %s where id = %s", (new_email, person.id))
    assert row(admin, "select email from public.profiles where id = %s", (person.id,))["email"] == new_email


def test_deleting_the_auth_user_removes_the_account_data_but_not_the_log(admin: Connection[DictRow]) -> None:
    person = create_user(admin, "beto", uuid.uuid4().hex[:10])
    admin.execute("delete from auth.users where id = %s", (person.id,))
    assert admin.execute("select 1 from public.profiles where id = %s", (person.id,)).fetchone() is None
    assert admin.execute("select 1 from public.business_profiles where owner_id = %s", (person.id,)).fetchone() is None
    # El registro de actividad es de solo inserción y no tiene clave foránea: sobrevive al borrado de la cuenta.
    assert admin.execute("select 1 from public.activity_log where owner_id = %s", (person.id,)).fetchone() is not None
