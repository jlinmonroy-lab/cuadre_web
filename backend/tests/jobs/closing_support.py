"""Ayudas de las pruebas del cierre mensual: relojes RELATIVOS al mes de alta de la cuenta de prueba (SPEC-W-012, hito 6).

El primer mes con actividad de una cuenta sin documentos es el de su alta, y la cuenta de prueba se crea con la hora real de la máquina. Una prueba que diga
«la cuenta nació en noviembre de 2026» deja de valer el 1 de diciembre. Estas ayudas leen el mes de alta de la base de datos y construyen el reloj a partir de él;
`SHIFTS` permite repetir la misma prueba con el alta desplazada a otro año (la base no se entera de qué hora real es).
"""

from datetime import UTC, date, datetime

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.closing import YearMonth
from tests.support import Person

# Sin desplazar (el alta real) y con el alta en marzo de 2031.
SHIFTS: list[datetime | None] = [None, datetime(2031, 3, 17, 10, 0, tzinfo=UTC)]


def signup_month(admin: Connection[DictRow], person: Person) -> YearMonth:
    """El mes de alta de la cuenta, en Europe/Madrid."""
    row = admin.execute(
        "select (created_at at time zone 'Europe/Madrid')::date as day from public.profiles where id = %s", (person.id,)
    ).fetchone()
    assert row is not None
    return YearMonth.of(row["day"])


def apply_shift(admin: Connection[DictRow], person: Person, shift: datetime | None) -> YearMonth:
    """Desplaza el alta de la cuenta (si se pide) y devuelve su mes de alta."""
    if shift is not None:
        admin.execute("update public.profiles set created_at = %s where id = %s", (shift, person.id))
    return signup_month(admin, person)


def first_of(month: YearMonth) -> datetime:
    """Las 08:00 UTC del día 1 del mes (09:00 o 10:00 en Madrid): ya es día 1 en Madrid."""
    return datetime(month.year, month.month, 1, 8, 0, tzinfo=UTC)


def day_of(month: YearMonth, day: int) -> date:
    return date(month.year, month.month, day)


def now_to_close(signup: YearMonth) -> datetime:
    """Una hora en la que el mes de alta ya ha terminado y es el último mes cerrable (el día 1 del siguiente)."""
    return first_of(signup.next())


def iso_to_close(signup: YearMonth, day: int = 5) -> str:
    """Lo mismo como texto para `--now` de la CLI (el día `day` del mes siguiente al alta)."""
    following = signup.next()
    return f"{following.year:04d}-{following.month:02d}-{day:02d}T08:00:00+00:00"
