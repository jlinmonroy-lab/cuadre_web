"""`python -m cuadre.cli create-admin` contra la pila REAL de Supabase (API de administración de Auth + service_role)."""

import os
import uuid

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre import cli
from tests.api.test_me_live import password_grant

pytestmark = pytest.mark.live

PASSWORD = "contraseña-de-prueba-123"


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch) -> None:
    if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        pytest.skip("Falta SUPABASE_SERVICE_ROLE_KEY (clave secreta de la pila local, en el .env)")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)


def new_email() -> str:
    return f"admin.{uuid.uuid4().hex[:10]}@example.test"


def audit(admin: Connection[DictRow], user_id: object) -> list[dict]:
    return admin.execute(
        "select actor_id, category, metadata from public.activity_log where owner_id = %s and action = 'account.role_changed'",
        (user_id,),
    ).fetchall()


@pytest.mark.usefixtures("cli_env")
def test_it_creates_a_working_admin_account_and_logs_it(
    admin: Connection[DictRow], capsys: pytest.CaptureFixture[str]
) -> None:
    email = new_email()
    assert cli.main(["create-admin", "--email", email, "--name", "Admin de prueba"]) == 0

    profile = admin.execute(
        "select id, role::text as role, display_name from public.profiles where email = %s", (email,)
    ).fetchone()
    assert profile is not None
    assert (profile["role"], profile["display_name"]) == ("admin", "Admin de prueba")
    assert audit(admin, profile["id"]) == [
        {"actor_id": None, "category": "account", "metadata": {"from": "usuario", "to": "admin", "via": "cli"}}
    ]

    # La cuenta puede iniciar sesión de verdad con esa contraseña.
    assert password_grant(email, PASSWORD).status_code == 200

    # Nunca se imprime la contraseña ni la clave de servicio.
    out = capsys.readouterr()
    assert PASSWORD not in out.out + out.err
    assert os.environ["SUPABASE_SERVICE_ROLE_KEY"] not in out.out + out.err


@pytest.mark.usefixtures("cli_env")
def test_it_is_idempotent(admin: Connection[DictRow], capsys: pytest.CaptureFixture[str]) -> None:
    email = new_email()
    assert cli.main(["create-admin", "--email", email]) == 0
    assert cli.main(["create-admin", "--email", email]) == 0
    assert "ya era administrador" in capsys.readouterr().out
    profile = admin.execute("select id from public.profiles where email = %s", (email,)).fetchone()
    assert profile is not None
    assert len(audit(admin, profile["id"])) == 1, "repetirlo no duplica el registro"


@pytest.mark.usefixtures("cli_env")
def test_it_promotes_an_existing_user_without_touching_their_password(admin: Connection[DictRow]) -> None:
    assert cli.main(["create-admin", "--email", "beto@example.test"]) == 0
    try:
        row = admin.execute(
            "select role::text as role from public.profiles where email = 'beto@example.test'"
        ).fetchone()
        assert row == {"role": "admin"}
        assert password_grant("beto@example.test").status_code == 200, "la contraseña del seed sigue valiendo"
    finally:  # el seed de desarrollo queda como estaba
        admin.execute("update public.profiles set role = 'usuario' where email = 'beto@example.test'")


@pytest.mark.parametrize(
    ("args", "env", "message"),
    [
        (["create-admin", "--email", "no-es-un-correo"], {"ADMIN_PASSWORD": PASSWORD}, "correo no es válido"),
        (["create-admin", "--email", "a@example.test"], {"ADMIN_PASSWORD": "corta"}, "al menos 10 caracteres"),
    ],
)
def test_it_validates_its_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    env: dict[str, str],
    message: str,
) -> None:
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "clave-falsa")
    monkeypatch.setenv("DATABASE_SERVICE_URL", "postgresql://nadie@127.0.0.1:1/x")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert cli.main(args) == 1
    assert message in capsys.readouterr().err


def test_it_reports_missing_configuration(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for var in ("SUPABASE_SERVICE_ROLE_KEY", "DATABASE_SERVICE_URL", "ADMIN_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(cli.Settings, "model_config", {**cli.Settings.model_config, "env_file": None})
    assert cli.main(["create-admin", "--email", "a@example.test"]) == 1
    err = capsys.readouterr().err
    assert all(v in err for v in ("SUPABASE_SERVICE_ROLE_KEY", "DATABASE_SERVICE_URL", "ADMIN_PASSWORD"))
