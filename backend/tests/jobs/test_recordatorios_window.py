"""AC-01, AC-02, AC-05 y AC-09 · Qué trimestre toca recordar (SPEC-W-014 §5.1, D-02). Python puro: sin base de datos."""

from datetime import UTC, date, datetime, timedelta

import pytest

from cuadre.core.clock import today_in_madrid
from cuadre.jobs.reminders import DueQuarter, due_quarter
from tests.clocks import FixedClock


def test_the_fourth_quarter_reminder_of_the_story() -> None:
    due = due_quarter(date(2027, 1, 20), 10)
    assert due == DueQuarter(year=2026, quarter=4, deadline=date(2027, 1, 30), days_left=10)
    assert due is not None and due.period == "2026-Q4"


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2027, 1, 19), None),
        (date(2027, 1, 20), "2026-Q4"),
        (date(2027, 1, 30), "2026-Q4"),  # el último día del plazo todavía se avisa
        (date(2027, 1, 31), None),
        (date(2026, 5, 15), None),  # entre plazos
    ],
)
def test_window_edges_with_ten_days(today: date, expected: str | None) -> None:
    due = due_quarter(today, 10)
    assert (due.period if due else None) == expected


@pytest.mark.parametrize(
    ("deadline", "period"),
    [
        (date(2026, 4, 20), "2026-Q1"),
        (date(2026, 7, 20), "2026-Q2"),
        (date(2026, 10, 20), "2026-Q3"),
        (date(2027, 1, 30), "2026-Q4"),
    ],
)
def test_the_four_deadlines(deadline: date, period: str) -> None:
    due = due_quarter(deadline - timedelta(days=10), 10)
    assert due is not None and (due.period, due.deadline, due.days_left) == (period, deadline, 10)
    assert due_quarter(deadline - timedelta(days=11), 10) is None
    assert due_quarter(deadline + timedelta(days=1), 10) is None


@pytest.mark.parametrize(("today", "expected"), [(date(2027, 1, 24), None), (date(2027, 1, 25), "2026-Q4")])
def test_a_custom_lead_of_five_days(today: date, expected: str | None) -> None:
    due = due_quarter(today, 5)
    assert (due.period if due else None) == expected


def test_the_lead_bounds() -> None:
    assert due_quarter(date(2027, 1, 29), 1) is not None
    assert due_quarter(date(2027, 1, 28), 1) is None
    assert due_quarter(date(2026, 12, 31), 30) is not None  # 30 de enero = 30 días después
    assert due_quarter(date(2026, 12, 30), 30) is None


@pytest.mark.parametrize("lead", [0, -1, 31, True, 10.0, "10", None])
def test_a_lead_outside_one_to_thirty_is_refused(lead: object) -> None:
    with pytest.raises(ValueError, match="entre 1 y 30"):
        due_quarter(date(2027, 1, 20), lead)  # type: ignore[arg-type]


def test_the_new_year_keeps_the_previous_fourth_quarter() -> None:
    for today in (date(2026, 12, 31), date(2027, 1, 1)):
        due = due_quarter(today, 30)
        assert due is not None and due.period == "2026-Q4"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2027, 1, 19, 23, 30, tzinfo=UTC), "2026-Q4"),  # 00:30 del 20 en Madrid (invierno, UTC+1)
        (datetime(2027, 1, 19, 22, 30, tzinfo=UTC), None),  # 23:30 del 19 en Madrid
        (datetime(2026, 7, 9, 22, 30, tzinfo=UTC), "2026-Q2"),  # 00:30 del 10 de julio en Madrid (verano, UTC+2)
        (datetime(2026, 7, 9, 21, 30, tzinfo=UTC), None),  # 23:30 del 9 de julio en Madrid
    ],
)
def test_the_day_is_the_one_in_madrid(now: datetime, expected: str | None) -> None:
    due = due_quarter(today_in_madrid(FixedClock(now)), 10)
    assert (due.period if due else None) == expected
