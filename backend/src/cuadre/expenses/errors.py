"""Errores de gastos en `application/problem+json` (SPEC-W-003 §5.3). `detail` en español, sin datos del documento ni del gasto."""

from cuadre.core.errors import ProblemError

# Qué dice cada campo de `invalid_expense` (los que puede señalar `app.create_manual_expense`).
FIELD_MESSAGES = {
    "expense_date": "La fecha no puede ser futura ni anterior al 1 de enero de 2000.",
    "concept": "Escribe un concepto de 1 a 200 caracteres.",
    "category": "Elige una categoría.",
    "amount_cents": "El importe debe ser mayor que cero.",
}


def validation_failed(failed_checks: list[str]) -> ProblemError:
    return ProblemError(
        422,
        "validation_failed",
        "Hay comprobaciones sin pasar",
        "Corrige los datos marcados y vuelve a intentarlo: no se ha registrado nada.",
        extra={"failed_checks": failed_checks},
    )


def suspicion_not_acknowledged() -> ProblemError:
    return ProblemError(
        422,
        "suspicion_not_acknowledged",
        "Falta confirmar la revisión",
        "El documento puede contener instrucciones ocultas. Compara los datos con el original y confírmalo para registrar el gasto.",
    )


def duplicate_expense() -> ProblemError:
    return ProblemError(
        409,
        "duplicate_expense",
        "Gasto duplicado",
        "Ya hay un gasto registrado con el mismo NIF del proveedor y el mismo número de factura.",
    )


def invalid_expense(field: str) -> ProblemError:
    return ProblemError(
        422,
        "invalid_expense",
        "Gasto no válido",
        FIELD_MESSAGES[field],
        extra={"field": field},
    )


def expense_not_found() -> ProblemError:
    return ProblemError(404, "expense_not_found", "Gasto no encontrado", "El gasto no existe.")


def expense_wrong_state() -> ProblemError:
    return ProblemError(409, "expense_wrong_state", "Gasto anulado", "Ese gasto ya está anulado y no admite cambios.")


def invalid_cursor() -> ProblemError:
    return ProblemError(
        422, "invalid_cursor", "Cursor no válido", "La página que pides ya no es válida. Vuelve a cargar la lista."
    )


def month_needs_year() -> ProblemError:
    return ProblemError(
        422,
        "validation_error",
        "Datos no válidos",
        "Revisa los datos enviados.",
        extra={"errors": [{"loc": "query.month", "msg": "El mes necesita el año."}]},
    )
