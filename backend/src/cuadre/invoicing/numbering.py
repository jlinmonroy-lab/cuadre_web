"""Número, series y orden de fechas (SPEC-W-007 §5.1.4, D-08, T7-03). Python puro."""

from datetime import date

from cuadre.invoicing.limits import NUMBER_MAX, NUMBER_MIN, NUMBER_MIN_DIGITS, RECTIFYING_CODE


def display_number(series_code: str, number: int) -> str:
    """`{serie}-{NNN}`: tres dígitos como mínimo (`2026-001`), sin relleno a partir de cuatro (`2026-1000`)."""
    if isinstance(number, bool) or not isinstance(number, int) or not NUMBER_MIN <= number <= NUMBER_MAX:
        raise ValueError(f"El número de una factura va de {NUMBER_MIN} a {NUMBER_MAX}.")
    if not series_code:
        raise ValueError("Falta el código de la serie.")
    return f"{series_code}-{number:0{NUMBER_MIN_DIGITS}d}"


def rectifying_series_code(year: int) -> str:
    """El código de la serie rectificativa del año: `R-2026`."""
    code = f"R-{year:04d}"
    if RECTIFYING_CODE.fullmatch(code) is None:
        raise ValueError(f"Año fuera de rango: {year}")
    return code


def is_reserved_series_code(code: str) -> bool:
    """Los códigos `R-AAAA` son de las series rectificativas: una serie ordinaria no puede usarlos."""
    return RECTIFYING_CODE.fullmatch(code) is not None


def is_out_of_order(issue_date: date, last_issue_date: date | None) -> bool:
    """La fecha no puede ser anterior a la de la última factura de la serie (la misma fecha vale)."""
    return last_issue_date is not None and issue_date < last_issue_date
