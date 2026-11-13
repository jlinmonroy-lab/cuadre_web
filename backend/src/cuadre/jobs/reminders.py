"""Recordatorio del plazo trimestral: la parte pura (SPEC-W-014 §5.1, D-01, D-02, D-04). Sin base de datos, sin red y sin reloj propio.

Quien llama pasa el «hoy en Europe/Madrid» (`cuadre.core.clock.today_in_madrid`). Aquí solo se decide QUÉ trimestre toca recordar y A QUIÉN; las cifras
las calcula el job con las mismas funciones que las pantallas, y la reserva en `reminder_log` evita duplicados.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from cuadre.tax.periods import filing_deadline

KIND = "quarter_deadline"
DEFAULT_ENABLED = True
DEFAULT_LEAD_DAYS = 10
MIN_LEAD_DAYS = 1
MAX_LEAD_DAYS = 30


@dataclass(frozen=True, slots=True)
class DueQuarter:
    """El trimestre cuyo plazo cae dentro de la ventana de aviso."""

    year: int
    quarter: int
    deadline: date
    days_left: int

    @property
    def period(self) -> str:
        """`2026-Q4`: la clave del trimestre en `reminder_log`."""
        return f"{self.year}-Q{self.quarter}"


def check_lead_days(lead_days: int) -> int:
    if isinstance(lead_days, bool) or not isinstance(lead_days, int) or not MIN_LEAD_DAYS <= lead_days <= MAX_LEAD_DAYS:
        raise ValueError(f"La antelación debe ser un entero entre {MIN_LEAD_DAYS} y {MAX_LEAD_DAYS} días.")
    return lead_days


def due_quarter(today: date, lead_days: int) -> DueQuarter | None:
    """El trimestre cuyo plazo de presentación está entre hoy y hoy + `lead_days` (ambos incluidos), o `None`.

    Se miran el año anterior y el actual porque el plazo del 4.º trimestre cae el 30 de enero del año siguiente. Con `lead_days` ≤ 30 y plazos separados
    por tres meses no puede haber dos; si los hubiera, gana el más cercano. Enviar cualquier día de la ventana (no solo el primero) hace que un día sin
    ejecución no pierda el aviso (D-02).
    """
    check_lead_days(lead_days)
    last = today + timedelta(days=lead_days)
    found = [
        (deadline, year, quarter)
        for year in (today.year - 1, today.year)
        for quarter in (1, 2, 3, 4)
        if today <= (deadline := filing_deadline(year, quarter)) <= last
    ]
    if not found:
        return None
    deadline, year, quarter = min(found)
    return DueQuarter(year=year, quarter=quarter, deadline=deadline, days_left=(deadline - today).days)


def effective_settings(row: dict[str, Any] | None) -> tuple[bool, int]:
    """`(enabled, lead_days)` de un usuario; sin fila en `reminder_settings` valen los de por defecto (D-01)."""
    if row is None:
        return DEFAULT_ENABLED, DEFAULT_LEAD_DAYS
    return bool(row["enabled"]), check_lead_days(row["lead_days"])


def is_recipient(*, role: str, status: str, enabled: bool, email: str | None) -> bool:
    """Solo reciben recordatorios las cuentas `usuario` activas con los avisos activados y un correo (D-04)."""
    return role == "usuario" and status == "active" and enabled and bool(email and email.strip())
