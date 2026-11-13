"""Operaciones de administración desde la terminal: `python -m cuadre.cli <comando>`.

Junto con `cuadre.jobs`, este es el único módulo que usa la clave de servicio de Supabase y `DATABASE_SERVICE_URL` (T-04).
Nunca imprime ni registra contraseñas ni claves.

Comandos:
    create-admin --email <correo> [--name <nombre>]
        Crea (o localiza) la cuenta y la promueve a administrador. La contraseña se lee de ADMIN_PASSWORD, no de un argumento,
        para que no quede en el historial de la terminal. Es idempotente: repetirlo no duplica nada ni cambia una contraseña existente.
    run-job <nombre> [--now <fecha ISO-8601 con zona>] [--user <uuid> ...]
        Ejecuta una tarea programada (`reminders`) a mano. `--now` simula la hora (por defecto, la actual); `--user` la limita a unas cuentas.
        Imprime solo contadores, nunca direcciones. Es idempotente. Termina con código 1 si algún envío falló.
"""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import httpx2 as httpx

from cuadre.config import Settings
from cuadre.db import open_pool, service_transaction
from cuadre.jobs.runner import JOB_NAMES, JobConfigurationError, UnknownJob, run_named_job
from cuadre.notifications import EmailConfigurationError, get_email_sender

MIN_PASSWORD_LENGTH = 10
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CliError(Exception):
    """Fallo esperado: se muestra el mensaje, sin traza, y el proceso termina con código 1."""


def _auth_headers(service_key: str) -> dict[str, str]:
    """Acepta la clave nueva `sb_secret_…` (solo cabecera `apikey`) o el JWT de servicio (también como Bearer)."""
    headers = {"apikey": service_key, "Content-Type": "application/json"}
    if service_key.count(".") == 2:
        headers["Authorization"] = f"Bearer {service_key}"
    return headers


def _create_auth_user(settings: Settings, email: str, password: str, name: str) -> bool:
    """Crea el usuario con la API de administración de Auth. Devuelve False si el correo ya existía."""
    assert settings.supabase_service_role_key is not None
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
        headers=_auth_headers(settings.supabase_service_role_key.get_secret_value()),
        json={"email": email, "password": password, "email_confirm": True, "user_metadata": {"display_name": name}},
        timeout=15,
    )
    if response.status_code in (200, 201):
        return True
    error_code = (
        response.json().get("error_code")
        if response.headers.get("content-type", "").startswith("application/json")
        else None
    )
    if response.status_code == 422 and error_code in ("email_exists", "user_already_exists"):
        return False
    # Solo el código de estado: el cuerpo podría repetir el correo o la contraseña enviados.
    raise CliError(
        f"La API de Auth rechazó la creación del usuario (HTTP {response.status_code}, {error_code or 'sin código'})."
    )


def _promote_to_admin(settings: Settings, email: str) -> tuple[UUID, str]:
    """Pone `admin` a la cuenta y lo registra. Devuelve (id, estado anterior del rol)."""
    assert settings.database_service_url is not None
    pool = open_pool(settings.database_service_url, name="cli", min_size=1, max_size=1)
    try:
        with service_transaction(pool) as conn:
            row = conn.execute(
                "SELECT id, role::text AS role FROM public.profiles WHERE email = %s", (email,)
            ).fetchone()
            if row is None:
                raise CliError("No existe ninguna cuenta con ese correo.")
            if row["role"] != "admin":
                conn.execute("UPDATE public.profiles SET role = 'admin' WHERE id = %s", (row["id"],))
                conn.execute(
                    "SELECT private.log_activity('account', NULL, NULL, %s, 'account.role_changed', 'profile', %s, %s::jsonb)",
                    (row["id"], str(row["id"]), json.dumps({"from": row["role"], "to": "admin", "via": "cli"})),
                )
            return row["id"], row["role"]
    finally:
        pool.close()


def create_admin(settings: Settings, email: str, name: str) -> int:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise CliError("El correo no es válido.")
    missing = [
        var
        for var, value in (
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
            ("DATABASE_SERVICE_URL", settings.database_service_url),
            ("ADMIN_PASSWORD", settings.admin_password),
        )
        if value is None
    ]
    if missing:
        raise CliError(f"Faltan variables de entorno: {', '.join(missing)}.")
    assert settings.admin_password is not None
    password = settings.admin_password.get_secret_value()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise CliError(f"ADMIN_PASSWORD debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")

    created = _create_auth_user(settings, email, password, name)
    user_id, previous = _promote_to_admin(settings, email)
    if created:
        outcome = "cuenta creada y promovida a administrador"
    elif previous != "admin":
        outcome = "la cuenta ya existía (su contraseña no se ha tocado) y se ha promovido a administrador"
    else:
        outcome = "la cuenta ya era administrador; no se ha cambiado nada"
    print(f"Listo: {outcome}.\n  correo: {email}\n  id:     {user_id}")
    return 0


def run_job(settings: Settings, name: str, now_text: str | None, users: Sequence[str]) -> int:
    if name not in JOB_NAMES:
        raise CliError(f"No existe esa tarea. Disponibles: {', '.join(JOB_NAMES)}.")
    try:
        now = datetime.fromisoformat(now_text) if now_text else datetime.now(UTC)
    except ValueError:
        raise CliError("--now debe ser una fecha ISO-8601, por ejemplo 2027-01-20T08:00:00+00:00.") from None
    if now.tzinfo is None:
        raise CliError("--now debe incluir la zona horaria, por ejemplo +00:00 o Z.")
    try:
        owners = [UUID(u) for u in users] or None
    except ValueError:
        raise CliError("--user debe ser un uuid.") from None
    try:
        sender = get_email_sender(settings)
    except EmailConfigurationError as exc:
        raise CliError(str(exc)) from None
    app_pool = open_pool(settings.database_url, name="cli-app", min_size=1, max_size=2)
    try:
        result = run_named_job(name, settings=settings, app_pool=app_pool, sender=sender, now=now, only_owners=owners)
    except (UnknownJob, JobConfigurationError) as exc:
        raise CliError(f"No se puede ejecutar la tarea ({type(exc).__name__}).") from None
    finally:
        app_pool.close()
    print(f"Listo: {result['sent']} enviados, {result['skipped']} omitidos, {result['failed']} fallidos.")
    return 1 if result["failed"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cuadre.cli", description="Administración de cuadre-web")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Crear (o localizar) una cuenta y hacerla administradora")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="Administrador", help="Nombre para mostrar (por defecto: Administrador)")
    job = commands.add_parser("run-job", help="Ejecutar una tarea programada a mano")
    job.add_argument("name", help=f"Tarea: {', '.join(JOB_NAMES)}")
    job.add_argument("--now", default=None, help="Hora simulada, ISO-8601 con zona (por defecto, la actual)")
    job.add_argument("--user", action="append", default=[], help="Limitar a esta cuenta (uuid); se puede repetir")
    args = parser.parse_args(argv)

    try:
        if args.command == "run-job":
            return run_job(Settings(), args.name, args.now, args.user)  # type: ignore[call-arg]
        return create_admin(Settings(), args.email, args.name)  # type: ignore[call-arg]
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
