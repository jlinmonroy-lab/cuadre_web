"""Errores de la API de la contabilidad mensual (SPEC-W-012 §5.3) en `application/problem+json` con `code` estable y `detail` en español.

Mismos códigos que los borradores trimestrales, con textos propios del mes. Ninguno repite lo que envió la persona ni datos de sus documentos.
"""

from cuadre.closing.limits import FIRST_YEAR, LAST_YEAR
from cuadre.core.errors import ProblemError


def invalid_period() -> ProblemError:
    return ProblemError(
        422,
        "invalid_period",
        "Periodo no válido",
        f"El año debe estar entre {FIRST_YEAR} y {LAST_YEAR} y el mes entre 1 y 12.",
    )


def period_in_future() -> ProblemError:
    return ProblemError(422, "period_in_future", "Mes futuro", "Ese mes todavía no ha empezado.")


def closing_not_found() -> ProblemError:
    return ProblemError(
        404, "closing_not_found", "Mes sin cierre", "Ese mes no se muestra: tu cuenta todavía no tenía actividad."
    )
