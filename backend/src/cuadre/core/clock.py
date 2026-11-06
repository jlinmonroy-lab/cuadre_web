"""Reloj inyectable (SPEC-W-003 §5.4). Las pruebas pasan uno fijo; SPEC-W-012 (cierre mensual) lo reutilizará.

Los validadores no ven el reloj: reciben el `today` que calcula `today_in_madrid`. Así la frontera de medianoche se prueba con una hora fija.
"""

from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


class Clock(Protocol):
    def now(self) -> datetime:
        """La hora actual, **con zona horaria**."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def today_in_madrid(clock: Clock) -> date:
    """El día de hoy en Europe/Madrid: a las 23:30 UTC del 31 de diciembre ya es 1 de enero."""
    now = clock.now()
    if now.tzinfo is None:
        raise ValueError("El reloj debe devolver una hora con zona horaria.")
    return now.astimezone(MADRID).date()
