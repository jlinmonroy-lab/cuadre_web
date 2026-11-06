"""Fecha de la factura (SPEC-W-003 §5.1): una fecha real, no anterior al 1 de enero de 2000 y no posterior a hoy en Europe/Madrid.

`today` ya llega calculado (`cuadre.core.clock.today_in_madrid`): aquí no se mira ningún reloj, así que la frontera de medianoche se
prueba con una fecha fija.
"""

from datetime import date

from cuadre.validators.limits import EARLIEST_DATE


def issue_date_problem(value: date | None, *, malformed: bool, today: date) -> str | None:
    """El motivo por el que la fecha no vale, o `None` si vale."""
    if malformed:
        return "La fecha no es válida: revisa el día, el mes y el año."
    if value is None:
        return "Falta la fecha de la factura."
    if value > today:
        return "La fecha es posterior a hoy."
    if value < EARLIEST_DATE:
        return "La fecha es anterior al 1 de enero de 2000."
    return None
