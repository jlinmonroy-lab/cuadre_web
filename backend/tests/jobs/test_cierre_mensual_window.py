"""AC-08, AC-09 y AC-10 (parte pura) · Qué meses toca cerrar (SPEC-W-012 §5.1, D-05, D-06). Python puro: sin base de datos."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from cuadre.closing import (
    FIRST_YEAR,
    InvalidMonth,
    YearMonth,
    closing_window,
    explicit_window,
    first_active_month,
    month_bounds,
    window_bounds,
)
from cuadre.core.clock import today_in_madrid
from cuadre.tax.periods import PeriodInFuture
from tests.clocks import FixedClock

SEP_2026 = YearMonth(2026, 9)


# --- El calendario ------------------------------------------------------------------------------------------------------------------------


def test_months_move_across_years() -> None:
    assert YearMonth(2026, 1).previous() == YearMonth(2025, 12)
    assert YearMonth(2025, 12).next() == YearMonth(2026, 1)
    assert YearMonth(2026, 3).shift(-14) == YearMonth(2025, 1)
    assert YearMonth(2026, 11).shift(14) == YearMonth(2028, 1)
    assert YearMonth(2026, 9).label == "2026-09" and YearMonth(2026, 12).label == "2026-12"
    assert YearMonth.of(date(2024, 2, 29)) == YearMonth(2024, 2)
    assert YearMonth(2025, 12) < YearMonth(2026, 1) < YearMonth(2026, 2)


@pytest.mark.parametrize(
    ("month", "start", "end"),
    [
        (YearMonth(2026, 9), date(2026, 9, 1), date(2026, 10, 1)),
        (YearMonth(2026, 12), date(2026, 12, 1), date(2027, 1, 1)),
        (YearMonth(2024, 2), date(2024, 2, 1), date(2024, 3, 1)),
        (YearMonth(2026, 2), date(2026, 2, 1), date(2026, 3, 1)),
    ],
)
def test_month_bounds(month: YearMonth, start: date, end: date) -> None:
    assert month_bounds(month) == (start, end)


def test_window_bounds_cover_the_whole_window() -> None:
    window = closing_window(date(2026, 10, 1), YearMonth(2020, 1))
    assert window_bounds(window) == (date(2025, 10, 1), date(2026, 10, 1))
    assert window_bounds([YearMonth(2026, 9), YearMonth(2026, 7)]) == (date(2026, 7, 1), date(2026, 10, 1))
    with pytest.raises(ValueError, match="vacía"):
        window_bounds([])


# --- AC-08 · El primer mes con actividad --------------------------------------------------------------------------------------------------


def test_the_first_active_month_is_the_oldest_of_the_dates_given() -> None:
    assert first_active_month(date(2026, 10, 14), date(2026, 3, 2), date(2026, 5, 30)) == YearMonth(2026, 3)
    assert first_active_month(date(2026, 10, 14), None, None) == YearMonth(2026, 10)
    assert first_active_month(None, None, date(2025, 12, 31)) == YearMonth(2025, 12)
    assert first_active_month(None, None) is None
    assert first_active_month() is None


def test_a_new_account_has_no_closings_before_its_first_month() -> None:
    first = first_active_month(date(2026, 10, 14))
    assert closing_window(date(2026, 11, 1), first) == (YearMonth(2026, 10),)
    assert closing_window(date(2026, 10, 20), first) == ()  # su primer mes aún no ha terminado
    assert closing_window(date(2026, 11, 1), None) == ()  # sin ninguna actividad


def test_an_account_with_older_invoices_closes_from_the_first_of_them() -> None:
    first = first_active_month(date(2026, 11, 3), date(2026, 3, 9))
    assert closing_window(date(2026, 11, 13), first) == tuple(YearMonth(2026, m) for m in range(3, 11))


# --- AC-09 · La ventana de 12 meses ------------------------------------------------------------------------------------------------------


def test_the_window_is_the_last_twelve_finished_months() -> None:
    window = closing_window(date(2026, 10, 1), YearMonth(2020, 1))
    assert len(window) == 12 and window[0] == YearMonth(2025, 10) and window[-1] == SEP_2026
    assert list(window) == sorted(window)


def test_the_current_month_is_never_in_the_window() -> None:
    assert closing_window(date(2026, 9, 30), YearMonth(2020, 1))[-1] == YearMonth(2026, 8)
    assert closing_window(date(2026, 10, 1), YearMonth(2020, 1))[-1] == SEP_2026


def test_in_january_the_window_ends_in_the_previous_december() -> None:
    window = closing_window(date(2027, 1, 1), YearMonth(2020, 1))
    assert window[-1] == YearMonth(2026, 12) and window[0] == YearMonth(2026, 1)


def test_the_window_is_cut_at_the_first_active_month_and_at_the_year_2000() -> None:
    assert closing_window(date(2026, 10, 1), YearMonth(2026, 7)) == (YearMonth(2026, 7), YearMonth(2026, 8), SEP_2026)
    assert closing_window(date(2026, 10, 1), SEP_2026) == (SEP_2026,)
    assert closing_window(date(2026, 10, 1), YearMonth(2026, 10)) == ()
    assert closing_window(date(2026, 10, 1), YearMonth(2027, 1)) == ()
    early = closing_window(date(2000, 3, 1), YearMonth(1990, 1), months=12)
    assert early == (YearMonth(FIRST_YEAR, 1), YearMonth(FIRST_YEAR, 2))


@pytest.mark.parametrize(("months", "length"), [(1, 1), (3, 3), (24, 24), (120, 120)])
def test_the_length_of_the_window_can_be_chosen(months: int, length: int) -> None:
    assert len(closing_window(date(2036, 10, 1), YearMonth(2020, 1), months=months)) == length


@pytest.mark.parametrize("months", [0, -1, 121, True, 12.0, "12", None])
def test_a_window_length_outside_one_to_a_hundred_and_twenty_is_refused(months: Any) -> None:
    with pytest.raises(ValueError, match="ventana"):
        closing_window(date(2026, 10, 1), YearMonth(2020, 1), months=months)


def test_an_explicit_month_may_be_outside_the_window() -> None:
    assert explicit_window(date(2026, 10, 1), 2026, 9) == (SEP_2026,)
    assert explicit_window(date(2026, 10, 1), 2023, 2) == (YearMonth(2023, 2),)  # hace más de 12 meses
    assert explicit_window(date(2026, 10, 1), 2000, 1) == (YearMonth(2000, 1),)


@pytest.mark.parametrize(("year", "month"), [(2026, 10), (2026, 11), (2027, 1), (9998, 12)])
def test_an_explicit_month_that_has_not_ended_is_in_the_future(year: int, month: int) -> None:
    with pytest.raises(PeriodInFuture):
        explicit_window(date(2026, 10, 15), year, month)


@pytest.mark.parametrize(
    ("year", "month"), [(1999, 12), (2026, 0), (2026, 13), (10000, 1), (True, 9), (2026, True), ("2026", 9)]
)
def test_an_explicit_month_that_does_not_exist_is_refused(year: Any, month: Any) -> None:
    with pytest.raises(InvalidMonth) as caught:
        explicit_window(date(2026, 10, 15), year, month)
    assert caught.value.code == "invalid_period"


# --- AC-10 · El día de Madrid y el cambio de año ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "last"),
    [
        (datetime(2026, 12, 31, 23, 30, tzinfo=UTC), YearMonth(2026, 12)),  # ya es 1 de enero en Madrid
        (datetime(2026, 12, 31, 22, 30, tzinfo=UTC), YearMonth(2026, 11)),  # todavía 31 de diciembre
        (datetime(2026, 9, 30, 22, 30, tzinfo=UTC), YearMonth(2026, 9)),  # verano (UTC+2): ya es 1 de octubre
        (datetime(2026, 9, 30, 21, 30, tzinfo=UTC), YearMonth(2026, 8)),
        (datetime(2027, 1, 1, 0, 0, tzinfo=UTC), YearMonth(2026, 12)),
    ],
)
def test_the_month_to_close_follows_the_day_in_madrid(now: datetime, last: YearMonth) -> None:
    window = closing_window(today_in_madrid(FixedClock(now)), YearMonth(2020, 1))
    assert window[-1] == last
