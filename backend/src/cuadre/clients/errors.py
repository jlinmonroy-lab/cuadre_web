"""Errores de clientes en `application/problem+json` (SPEC-W-006 §5.3). `detail` en español.

Ninguno repite lo que escribió la persona (NFR-11, T6-04): dicen qué campo falla y por qué, no con qué valor. El nombre, el NIF y el domicilio de
un cliente son datos de un tercero.
"""

from cuadre.clients.types import FieldError
from cuadre.core.errors import ProblemError


def invalid_client(errors: tuple[FieldError, ...]) -> ProblemError:
    return ProblemError(
        422,
        "invalid_client",
        "Cliente no válido",
        "Revisa los campos marcados: no se ha guardado nada.",
        extra={"fields": [{"field": e.field, "message": e.message} for e in errors]},
    )


def client_tax_id_taken() -> ProblemError:
    return ProblemError(
        409,
        "client_tax_id_taken",
        "Identificador en uso",
        "Ya tienes otro cliente activo con ese NIF o identificador fiscal.",
    )


def client_archived() -> ProblemError:
    return ProblemError(
        409, "client_archived", "Cliente archivado", "Un cliente archivado no se puede editar: reactívalo primero."
    )


def client_not_found() -> ProblemError:
    return ProblemError(404, "client_not_found", "Cliente no encontrado", "El cliente no existe.")
