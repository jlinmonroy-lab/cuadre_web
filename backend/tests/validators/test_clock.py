"""AC-05 · El día de hoy en Europe/Madrid, con un reloj fijo (SPEC-W-003 §5.4)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from cuadre.core.clock import MADRID, Clock, SystemClock, today_in_madrid
from cuadre.validators import InvoiceData, TaxLine, ValidationContext, validate
from cuadre.validators.dates import issue_date_problem
from tests.clocks import FixedClock


def madrid_today(*parts: int) -> date:
    return today_in_madrid(FixedClock(datetime(*parts, tzinfo=UTC)))


def test_at_23_30_utc_on_new_years_eve_it_is_already_january_first_in_madrid() -> None:
    assert madrid_today(2026, 12, 31, 23, 30) == date(2027, 1, 1)
    assert madrid_today(2026, 12, 31, 22, 59) == date(2026, 12, 31)
    assert madrid_today(2026, 12, 31, 23, 0) == date(2027, 1, 1)


def test_the_boundary_in_summer_time_is_at_22_utc() -> None:
    assert madrid_today(2026, 6, 30, 21, 59) == date(2026, 6, 30)
    assert madrid_today(2026, 6, 30, 22, 0) == date(2026, 7, 1)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        ((2026, 3, 28, 23, 30), date(2026, 3, 29)),  # la noche del cambio a la hora de verano: aún +1, ya es 29
        ((2026, 3, 29, 0, 30), date(2026, 3, 29)),
        ((2026, 3, 29, 22, 30), date(2026, 3, 30)),  # ya +2
        ((2026, 10, 24, 22, 30), date(2026, 10, 25)),  # aún +2
        ((2026, 10, 25, 22, 30), date(2026, 10, 25)),  # tras el cambio, +1: sigue siendo el 25
        ((2026, 10, 25, 23, 0), date(2026, 10, 26)),
    ],
)
def test_daylight_saving_changes_do_not_move_the_day(moment: tuple[int, ...], expected: date) -> None:
    assert madrid_today(*moment) == expected


def test_a_clock_in_another_time_zone_is_converted() -> None:
    new_york = timezone(timedelta(hours=-5))
    clock = FixedClock(datetime(2026, 12, 31, 18, 30, tzinfo=new_york))  # son las 23:30 UTC
    assert today_in_madrid(clock) == date(2027, 1, 1)


def test_a_naive_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        today_in_madrid(FixedClock(datetime(2026, 11, 6, 12, 0)))


def test_the_system_clock_returns_an_aware_time_close_to_now() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert abs(now - datetime.now(UTC)) < timedelta(seconds=5)
    assert isinstance(today_in_madrid(SystemClock()), date)


def test_a_fixed_clock_satisfies_the_clock_protocol() -> None:
    clock: Clock = FixedClock(datetime(2026, 11, 6, tzinfo=MADRID))
    assert clock.now().tzinfo is MADRID


def test_the_madrid_boundary_decides_the_validation_of_an_invoice_dated_the_first_of_january() -> None:
    """Con el reloj a las 23:30 UTC del 31 de diciembre, una factura del 1 de enero pasa y una del 2 de enero no."""
    today = madrid_today(2026, 12, 31, 23, 30)
    assert issue_date_problem(date(2027, 1, 1), malformed=False, today=today) is None
    assert issue_date_problem(date(2027, 1, 2), malformed=False, today=today) is not None


def test_validate_gets_today_from_the_context_and_never_from_a_clock() -> None:
    data = InvoiceData(
        doc_type="full_invoice",
        supplier_name="Nubesoft S.L.",
        supplier_tax_id="B00000042",
        invoice_number="NS-1",
        issue_date=date(2027, 1, 1),
        currency="EUR",
        tax_lines=(TaxLine("21", 2479, 521),),
        total_cents=3000,
    )
    before = validate(data, ValidationContext(today=date(2026, 12, 31)))
    after = validate(data, ValidationContext(today=madrid_today(2026, 12, 31, 23, 30)))
    assert not before.can_register and after.can_register
