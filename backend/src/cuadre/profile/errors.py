"""Errores del perfil, las series y el logo en `application/problem+json` (SPEC-W-005 §5.3). `detail` en español.

Ninguno repite lo que escribió la persona (NFR-11, T5-05): dicen qué campo falla y por qué, no con qué valor.
"""

from cuadre.core.errors import ProblemError
from cuadre.profile.types import FieldError


def invalid_profile(errors: tuple[FieldError, ...]) -> ProblemError:
    return ProblemError(
        422,
        "invalid_profile",
        "Perfil no válido",
        "Revisa los campos marcados: no se ha guardado nada.",
        extra={"fields": [{"field": e.field, "message": e.message} for e in errors]},
    )


def invalid_series(field: str, message: str) -> ProblemError:
    return ProblemError(422, "invalid_series", "Serie no válida", message, extra={"field": field})


def series_code_taken() -> ProblemError:
    return ProblemError(
        409, "series_code_taken", "Código en uso", "Ya tienes una serie con ese código (también entre las archivadas)."
    )


def series_in_use() -> ProblemError:
    return ProblemError(
        409,
        "series_in_use",
        "Serie en uso",
        "Esa serie ya tiene facturas emitidas: su código y su número inicial no se pueden cambiar.",
    )


def series_is_default() -> ProblemError:
    return ProblemError(
        409, "series_is_default", "Serie predeterminada", "Elige otra serie como predeterminada antes de archivar esta."
    )


def series_archived() -> ProblemError:
    return ProblemError(
        409,
        "series_archived",
        "Serie archivada",
        "Una serie archivada no puede ser la predeterminada: reactívala antes.",
    )


def series_not_found() -> ProblemError:
    return ProblemError(404, "series_not_found", "Serie no encontrada", "La serie no existe.")


def logo_unsupported_type() -> ProblemError:
    return ProblemError(
        415, "logo_unsupported_type", "Tipo de imagen no admitido", "El logo tiene que ser una imagen PNG, JPEG o WebP."
    )


def logo_too_large() -> ProblemError:
    return ProblemError(413, "logo_too_large", "Logo demasiado grande", "El logo no puede pesar más de 1 MiB.")


def logo_invalid() -> ProblemError:
    return ProblemError(
        422,
        "logo_invalid",
        "Logo no válido",
        "No hemos recibido el logo, o no es una imagen del tipo indicado. Súbelo de nuevo.",
    )


def logo_not_found() -> ProblemError:
    return ProblemError(404, "logo_not_found", "Sin logo", "Todavía no has subido un logo.")
