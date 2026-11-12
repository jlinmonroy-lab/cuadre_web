"""Qué `EmailSender` usa la aplicación según el entorno (SPEC-W-010 T10-10, ADR-0008)."""

import logging

from cuadre.config import Settings
from cuadre.notifications.senders import ConsoleEmailSender, UnavailableEmailSender
from cuadre.notifications.types import EmailConfigurationError, EmailSender

logger = logging.getLogger("cuadre.notifications")


def get_email_sender(settings: Settings) -> EmailSender:
    """`EMAIL_PROVIDER=console` (por defecto) escribe en consola. Con `APP_ENV=production` no se finge: todavía no hay proveedor real (DEP-05), así que se
    avisa al arrancar y cada envío falla de forma explícita (la API sigue funcionando y la invitación sale con `email_sent: false`). Un proveedor que no
    existe es un error de configuración."""
    provider = settings.email_provider
    if provider == "console":
        if settings.app_env == "production":
            logger.warning("email_provider_missing")
            return UnavailableEmailSender()
        return ConsoleEmailSender()
    raise EmailConfigurationError(f"EMAIL_PROVIDER «{provider}» no está implementado.")
