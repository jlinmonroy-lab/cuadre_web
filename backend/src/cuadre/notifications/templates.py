"""Plantillas de los correos (en español). Sin tokens, sin enlaces firmados y sin ningún dato financiero (SPEC-W-010 D-01, T10-06)."""

from datetime import date

from cuadre.invoicing.texts import MONTHS, format_euros, long_date
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


# --- Recordatorio del plazo trimestral (SPEC-W-014 §5.1) -------------------------------------------------------------------------------------

QUARTER_REMINDER_KIND = "quarter_reminder"

_RESULT_303 = {
    "a_ingresar": "a ingresar",
    "a_compensar": "a compensar en próximos trimestres",
}
_RESULT_130 = {"a_ingresar": "a ingresar"}


def _model_line(label: str, cents: int, kind: str, labels: dict[str, str]) -> str:
    if kind == "sin_actividad":
        return f"  · Modelo {label}: sin actividad en el trimestre."
    if kind in labels:
        return f"  · Modelo {label}: {labels[kind]}, {format_euros(abs(cents))}."
    return f"  · Modelo {label}: resultado a cero, sin importe a ingresar."


def _days_left(days: int) -> str:
    if days == 0:
        return "El plazo termina hoy."
    if days == 1:
        return "Queda 1 día para presentar."
    return f"Quedan {days} días para presentar."


def _pending(count: int) -> str:
    if count == 0:
        return "No tienes facturas pendientes de revisar."
    if count == 1:
        return "Tienes 1 factura pendiente de revisar."
    return f"Tienes {count} facturas pendientes de revisar."


def quarter_reminder(
    *,
    to: str,
    name: str,
    year: int,
    quarter: int,
    deadline: date,
    days_left: int,
    modelo_303: tuple[int, str],
    modelo_130: tuple[int, str],
    pending_documents: int,
    app_url: str,
) -> EmailMessage:
    """Aviso del plazo de los modelos 303 y 130. Las cifras llegan ya calculadas (`cuadre.tax`), en céntimos enteros; aquí solo se redactan.

    Sin IBAN, NIF, clientes ni enlaces firmados: únicamente el enlace a la aplicación. Todo es orientativo y no se presenta nada ante la AEAT.
    """
    greeting = f"Hola, {name.strip()}:" if name.strip() else "Hola:"
    link = f"{app_url.rstrip('/')}/trimestres"
    text = (
        f"{greeting}\n\n"
        f"El plazo para presentar los modelos 303 y 130 del {quarter}T {year} termina el {long_date(deadline)}. {_days_left(days_left)}\n\n"
        "Importes estimados con lo que has registrado:\n"
        f"{_model_line('303', *modelo_303, _RESULT_303)}\n"
        f"{_model_line('130', *modelo_130, _RESULT_130)}\n\n"
        f"{_pending(pending_documents)}\n\n"
        f"Revisa el detalle en {link}\n\n"
        "Cifras orientativas: Cuadre no presenta nada ante la AEAT. Confírmalas con tu gestor o asesor antes de presentar.\n"
    )
    subject = f"Plazo del {quarter}T {year} (modelos 303 y 130): {deadline.day} de {MONTHS[deadline.month - 1]}"
    return EmailMessage(to=to, subject=subject, text=text, kind=QUARTER_REMINDER_KIND)
