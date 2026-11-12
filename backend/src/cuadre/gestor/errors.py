"""Errores del acceso del gestor en `application/problem+json` (SPEC-W-010 §5.3). `detail` en español.

Ninguno repite lo que envió la persona (el correo de un gestor es un dato de un tercero) ni revela si una cuenta existe (T10-04).
"""

from cuadre.core.errors import ProblemError

INVITATION_LIMIT = 5


def invalid_email() -> ProblemError:
    return ProblemError(422, "invalid_email", "Correo no válido", "Escribe un correo electrónico válido.")


def cannot_invite_self() -> ProblemError:
    return ProblemError(422, "cannot_invite_self", "Invitación no válida", "No puedes invitarte a ti mismo.")


def invitation_already_open() -> ProblemError:
    return ProblemError(
        409,
        "invitation_already_open",
        "Invitación ya abierta",
        "Ya hay una invitación pendiente o un acceso activo para ese correo.",
    )


def too_many_open_invitations() -> ProblemError:
    return ProblemError(
        422,
        "too_many_open_invitations",
        "Demasiadas invitaciones abiertas",
        f"Ya tienes {INVITATION_LIMIT} invitaciones o accesos abiertos. Revoca alguno para invitar a otra persona.",
    )


def gestor_access_not_found() -> ProblemError:
    return ProblemError(404, "gestor_access_not_found", "Acceso no encontrado", "Ese acceso o invitación no existe.")


def gestor_access_not_open() -> ProblemError:
    return ProblemError(
        409, "gestor_access_not_open", "Acceso ya cerrado", "Ese acceso ya no está abierto: no hay nada que revocar."
    )


def gestor_access_not_pending() -> ProblemError:
    return ProblemError(
        409, "gestor_access_not_pending", "Invitación ya respondida", "Esa invitación ya no está pendiente."
    )


def gestor_access_expired() -> ProblemError:
    return ProblemError(
        409, "gestor_access_expired", "Invitación caducada", "Esa invitación ha caducado: pide que te inviten de nuevo."
    )
