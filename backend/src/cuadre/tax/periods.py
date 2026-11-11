"""Trimestres naturales y plazos de presentación del modelo 303 (SPEC-W-008 §5.1, D-02). Python puro: recibe fechas, nunca lee un reloj.

Quien llama pasa el «hoy en Europe/Madrid» (`cuadre.core.clock.today_in_madrid`) y las fechas de expedición o de gasto, que ya son fechas de
calendario. El trimestre es el natural (enero-marzo, abril-junio, julio-septiembre y octubre-diciembre).
"""

from datetime import date

from cuadre.tax.limits import FILING_DEADLINES, PERIOD_MAX_YEAR, PERIOD_MIN_YEAR
from cuadre.tax.types_303 import DeadlineStatus


class InvalidPeriod(ValueError):
    """El año o el trimestre no existen (año fuera de 2000-9998 o trimestre fuera de 1-4)."""

    code = "invalid_period"


class PeriodInFuture(ValueError):
    """El trimestre todavía no ha empezado."""

    code = "period_in_future"


def quarter_of(day: date) -> tuple[int, int]:
    """El año y el trimestre (1 a 4) al que pertenece una fecha."""
    return day.year, (day.month - 1) // 3 + 1


def year_start(year: int) -> date:
    """El 1 de enero: el modelo 130 acumula desde ahí hasta el fin del trimestre (SPEC-W-009 D-02)."""
    return date(year, 1, 1)


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    """El primer día del trimestre y el primero del siguiente (el final es exclusivo)."""
    start = date(year, 3 * quarter - 2, 1)
    end = date(year + 1, 1, 1) if quarter == 4 else date(year, 3 * quarter + 1, 1)
    return start, end


def filing_deadline(year: int, quarter: int) -> date:
    """El último día para presentar el trimestre: 20 de abril, julio y octubre, y 30 de enero del año siguiente."""
    month, day = FILING_DEADLINES[quarter]
    return date(year + 1 if quarter == 4 else year, month, day)


def deadline_status(year: int, quarter: int, today: date) -> DeadlineStatus:
    """`en_curso` mientras el trimestre no ha terminado, `plazo_abierto` hasta el último día del plazo (incluido) y `plazo_cerrado` después."""
    _, end = quarter_bounds(year, quarter)
    if today < end:
        return "en_curso"
    return "plazo_abierto" if today <= filing_deadline(year, quarter) else "plazo_cerrado"


def validate_period(year: int, quarter: int, today: date) -> None:
    """Falla con `InvalidPeriod` si el periodo no existe y con `PeriodInFuture` si el trimestre aún no ha empezado."""
    valid = (
        isinstance(year, int)
        and isinstance(quarter, int)
        and not isinstance(quarter, bool)  # `True` vale 1 y pasaría el rango del trimestre; el del año ya lo rechaza
        and PERIOD_MIN_YEAR <= year <= PERIOD_MAX_YEAR
        and 1 <= quarter <= 4
    )
    if not valid:
        raise InvalidPeriod(
            f"El año debe estar entre {PERIOD_MIN_YEAR} y {PERIOD_MAX_YEAR} y el trimestre entre 1 y 4."
        )
    start, _ = quarter_bounds(year, quarter)
    if start > today:
        raise PeriodInFuture("Ese trimestre todavía no ha empezado.")
