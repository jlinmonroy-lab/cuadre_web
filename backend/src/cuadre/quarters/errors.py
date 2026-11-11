"""Errores de la API de los modelos 303 y 130 (SPEC-W-008 y SPEC-W-009, §5.3) en `application/problem+json` con `code` estable y `detail` en español.

Ninguno repite lo que envió la persona ni datos de sus documentos (T8-06).
"""

from cuadre.core.errors import ProblemError
from cuadre.tax.limits import PERIOD_MAX_YEAR, PERIOD_MIN_YEAR, QUARTER_MAX_DOCUMENTS, YEAR_MAX_DOCUMENTS


def invalid_period() -> ProblemError:
    return ProblemError(
        422,
        "invalid_period",
        "Periodo no válido",
        f"El año debe estar entre {PERIOD_MIN_YEAR} y {PERIOD_MAX_YEAR} y el trimestre entre 1 y 4.",
    )


def period_in_future() -> ProblemError:
    return ProblemError(422, "period_in_future", "Trimestre futuro", "Ese trimestre todavía no ha empezado.")


def quarter_too_large() -> ProblemError:
    limit = f"{QUARTER_MAX_DOCUMENTS:,}".replace(",", ".")
    return ProblemError(
        422,
        "quarter_too_large",
        "Trimestre demasiado grande",
        f"El trimestre tiene más de {limit} documentos y no cabe en el borrador.",
    )


def unsupported_vat_rate() -> ProblemError:
    return ProblemError(
        422,
        "unsupported_vat_rate",
        "Dato no válido en un documento",
        "Algún documento del trimestre trae un tipo de IVA que no se puede interpretar. "
        "Revisa tus facturas y gastos de este trimestre.",
    )


def period_too_large() -> ProblemError:
    """El 130 acumula desde enero: mismo `code` estable que el 303 y un texto que habla del periodo, no del trimestre."""
    limit = f"{YEAR_MAX_DOCUMENTS:,}".replace(",", ".")
    return ProblemError(
        422,
        "quarter_too_large",
        "Periodo demasiado grande",
        f"El periodo acumulado desde el 1 de enero tiene más de {limit} documentos y no cabe en el borrador.",
    )
