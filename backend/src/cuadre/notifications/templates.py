"""Plantillas de los correos (en español). Sin tokens, sin enlaces firmados y sin ningún dato financiero (SPEC-W-010 D-01, T10-06)."""

from cuadre.notifications.types import EmailMessage

GESTOR_INVITATION_SUBJECT = "Te han invitado a dar acceso a su contabilidad en Cuadre"


def gestor_invitation(*, to: str, owner_name: str, app_url: str, days_valid: int = 14) -> EmailMessage:
    """La invitación de un autónomo a su gestor. El mensaje es el mismo para cualquier destinatario: no revela si la dirección es de una cuenta."""
    who = owner_name.strip() or "Una persona"
    text = (
        f"{who} te ha invitado a dar acceso a su contabilidad en Cuadre.\n\n"
        f"Entra con tu cuenta de gestor en {app_url}, abre «Cartera» y acepta la invitación. "
        "Si no esperabas este correo, puedes ignorarlo: sin tu aceptación no se comparte nada.\n\n"
        f"La invitación caduca a los {days_valid} días.\n"
    )
    return EmailMessage(to=to, subject=GESTOR_INVITATION_SUBJECT, text=text, kind="gestor_invitation")
