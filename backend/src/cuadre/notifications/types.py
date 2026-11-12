"""Tipos del correo transaccional (SPEC-W-010 T10-10, ADR-0008). Sin proveedor real todavía (DEP-05)."""

from dataclasses import dataclass
from typing import Protocol


class EmailDeliveryError(Exception):
    """El correo no se pudo entregar al proveedor. Nunca lleva la dirección ni el cuerpo."""


class EmailConfigurationError(Exception):
    """La configuración del correo no permite arrancar (por ejemplo, producción sin proveedor)."""


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Un correo ya redactado. `kind` identifica la plantilla (`gestor_invitation`): es lo único del mensaje que puede ir a un registro."""

    to: str
    subject: str
    text: str
    kind: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None:
        """Entrega el mensaje o lanza `EmailDeliveryError`."""
        ...
