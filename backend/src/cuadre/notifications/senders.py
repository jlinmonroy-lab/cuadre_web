"""Los envíos del correo: consola (desarrollo) y memoria (pruebas). El proveedor real queda sin implementar (ADR-0008, DEP-05)."""

import logging

from cuadre.notifications.types import EmailDeliveryError, EmailMessage

logger = logging.getLogger("cuadre.notifications")


def mask_address(address: str) -> str:
    """`gestora@example.test` -> `g***@example.test`: lo bastante para depurar en local sin dejar el correo entero en un registro."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


class ConsoleEmailSender:
    """Desarrollo: no envía nada; deja una línea con el destinatario enmascarado y el tipo de mensaje. **Nunca** el asunto ni el cuerpo."""

    def send(self, message: EmailMessage) -> None:
        logger.info("email_console", extra={"to": mask_address(message.to), "kind": message.kind})


class UnavailableEmailSender:
    """Producción sin proveedor real (DEP-05): no finge enviar. Cada envío falla, y la invitación lo dice (`email_sent: false`) sin dejar de existir."""

    def send(self, message: EmailMessage) -> None:
        raise EmailDeliveryError("no hay un proveedor de correo configurado")


class MemoryEmailSender:
    """Pruebas: guarda lo enviado para hacer aserciones. Con `fail=True` simula un proveedor caído."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[EmailMessage] = []
        self.fail = fail

    def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise EmailDeliveryError("proveedor de correo no disponible")
        self.sent.append(message)
