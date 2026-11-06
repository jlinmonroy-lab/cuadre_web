"""Relojes para las pruebas (SPEC-W-003 §5.4). Separado de `tests/support.py`, que es de utilidades de base de datos."""

from datetime import datetime


class FixedClock:
    """Un `cuadre.core.clock.Clock` que siempre devuelve la misma hora."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now
