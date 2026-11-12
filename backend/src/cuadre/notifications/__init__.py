"""Correo transaccional detrás de una interfaz (ADR-0008, SPEC-W-010). Sin proveedor real: consola en desarrollo y memoria en las pruebas."""

from cuadre.notifications.selection import get_email_sender
from cuadre.notifications.senders import ConsoleEmailSender, MemoryEmailSender, UnavailableEmailSender, mask_address
from cuadre.notifications.templates import GESTOR_INVITATION_SUBJECT, gestor_invitation
from cuadre.notifications.types import EmailConfigurationError, EmailDeliveryError, EmailMessage, EmailSender

__all__ = [
    "GESTOR_INVITATION_SUBJECT",
    "ConsoleEmailSender",
    "EmailConfigurationError",
    "EmailDeliveryError",
    "EmailMessage",
    "EmailSender",
    "MemoryEmailSender",
    "UnavailableEmailSender",
    "get_email_sender",
    "gestor_invitation",
    "mask_address",
]
