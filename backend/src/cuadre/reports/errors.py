"""Errores de la API del reporte mensual (SPEC-W-013 §5.3) en `application/problem+json` con `code` estable y `detail` en español.

Los de periodo son los de la contabilidad mensual (mismos códigos y textos). Ninguno repite lo que envió la persona ni datos de sus documentos.
"""

from cuadre.closing.errors import closing_not_found, invalid_period, period_in_future
from cuadre.core.errors import ProblemError

__all__ = ["closing_not_found", "invalid_period", "period_in_future", "report_too_large"]


def report_too_large() -> ProblemError:
    return ProblemError(
        422, "report_too_large", "Reporte demasiado grande", "Ese mes tiene más gastos de los que caben en un reporte."
    )
