"""Errores de facturas en `application/problem+json` (SPEC-W-007 §5.3). `detail` en español.

Ninguno repite lo que escribió la persona (NFR-11, T7-06): dicen qué campo falla y por qué, no con qué valor. El nombre, el NIF, el domicilio, el IBAN y
el concepto de una factura son datos de terceros o personales. Los textos de los problemas del dominio son los de `cuadre.invoicing.MESSAGES`.
"""

from datetime import date

from cuadre.core.errors import ProblemError
from cuadre.invoicing.rules import MESSAGES
from cuadre.invoicing.texts import numeric_date
from cuadre.invoicing.types import FieldError, Problem

TITLES = {
    "client_not_billable": "Cliente no facturable",
    "irpf_rate_missing": "Falta la retención de IRPF",
    "invoice_date_out_of_order": "Fecha fuera de orden",
    "rectification_exceeds": "La rectificativa no puede subir el importe",
    "invoice_not_rectifiable": "Factura no rectificable",
}


def invalid_invoice(errors: tuple[FieldError, ...]) -> ProblemError:
    return ProblemError(
        422,
        "invalid_invoice",
        "Factura no válida",
        "Revisa los campos marcados: no se ha emitido nada.",
        extra={"fields": [{"field": e.field, "message": e.message} for e in errors]},
    )


def profile_incomplete(missing: list[tuple[str, str]]) -> ProblemError:
    """`missing` son pares (campo, etiqueta) de lo que falta en el perfil para poder emitir (US-007)."""
    return ProblemError(
        422,
        "profile_incomplete",
        "Perfil incompleto",
        "Completa tu perfil para poder emitir facturas.",
        extra={"missing": [{"field": field, "label": label} for field, label in missing]},
    )


def from_problem(problem: Problem) -> ProblemError:
    """Un problema del dominio (cliente archivado o sin domicilio, retención sin elegir, fecha fuera de orden, rectificativa que sube…)."""
    extra = {"field": problem.field} if problem.field is not None else None
    title = TITLES.get(problem.code, "Factura no emitida")
    return ProblemError(problem.status, problem.code, title, problem.message, extra=extra)


def invoice_not_found() -> ProblemError:
    return ProblemError(404, "invoice_not_found", "Factura no encontrada", "La factura no existe.")


def invoice_not_payable() -> ProblemError:
    return ProblemError(
        409, "invoice_not_payable", "Factura no cobrable", "Una factura rectificativa no se cobra: cobra la original."
    )


def invoice_changed() -> ProblemError:
    return ProblemError(
        409,
        "invoice_changed",
        "La factura ha cambiado",
        "Otra rectificación ha cambiado la factura mientras la rectificabas. Ábrela de nuevo y vuelve a intentarlo.",
    )


def invoice_pdf_pending() -> ProblemError:
    return ProblemError(
        409,
        "invoice_pdf_pending",
        "PDF pendiente",
        "Esta factura aún no tiene PDF. Genéralo y vuelve a descargarlo.",
    )


def invoice_pdf_corrupt() -> ProblemError:
    return ProblemError(
        409,
        "invoice_pdf_corrupt",
        "PDF alterado",
        "El archivo guardado no coincide con la huella registrada, así que no se entrega. La factura no ha cambiado.",
    )


def series_exhausted() -> ProblemError:
    return ProblemError(
        409,
        "series_exhausted",
        "Serie agotada",
        "La serie ha llegado al último número posible: elige otra serie.",
        extra={"field": "series_id"},
    )


def not_billable(detail: str) -> ProblemError:
    """`client_not_billable` que llega de la base (alguien archivó al cliente entre la lectura y la emisión)."""
    if detail == "address":
        return from_problem(Problem("client_not_billable", 409, MESSAGES["client_address"], "address"))
    return from_problem(Problem("client_not_billable", 409, MESSAGES["client_archived"], "client_id"))


def date_out_of_order(detail: str) -> ProblemError:
    """`invoice_date_out_of_order` que llega de la base: `detail` es la fecha de referencia en ISO (la de la última factura de la serie o la de la
    original, según el caso). La base no dice cuál, así que el texto vale para las dos."""
    try:
        message = f"La fecha no puede ser anterior al {numeric_date(date.fromisoformat(detail))}."
    except ValueError:
        message = "La fecha no puede ser anterior a la de la última factura de la serie."
    return from_problem(Problem("invoice_date_out_of_order", 409, message, "issue_date"))
