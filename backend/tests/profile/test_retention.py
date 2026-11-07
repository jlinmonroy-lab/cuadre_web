"""AC-04 · Sugerencia y aviso de la retención (D-04, §5.1): el 7 % vale el año del alta y los dos siguientes. Orientativo."""

from datetime import date
from decimal import Decimal

import pytest

from cuadre.profile import Retention, retention
from cuadre.profile.rules import WARNING_NO_START_DATE, WARNING_OUT_OF_PERIOD

TODAY = date(2026, 11, 7)
SEVEN = Decimal("7.00")
FIFTEEN = Decimal("15.00")


@pytest.mark.parametrize(
    ("start", "until", "suggested"),
    [
        (date(2026, 3, 1), 2028, "7.00"),  # este año
        (date(2025, 1, 15), 2027, "7.00"),
        (date(2024, 12, 31), 2026, "7.00"),  # el último año de la ventana: aún 7 %
        (date(2024, 1, 1), 2026, "7.00"),
        (date(2023, 12, 31), 2025, "15.00"),  # un año después de la ventana
        (date(2020, 6, 1), 2022, "15.00"),
        (date(2027, 1, 1), 2029, "7.00"),  # un alta en el futuro (hasta un año)
    ],
)
def test_the_suggestion_follows_the_start_year(start: date, until: int, suggested: str) -> None:
    result = retention(start, None, TODAY)
    assert (result.reduced_until_year, result.suggested_rate) == (until, suggested)
    assert result.warning is None  # sin retención elegida, no hay nada que avisar


def test_the_window_closes_on_new_year() -> None:
    start = date(2024, 12, 31)
    assert retention(start, None, date(2026, 12, 31)).suggested_rate == "7.00"
    assert retention(start, None, date(2027, 1, 1)).suggested_rate == "15.00"
    assert retention(start, None, date(2027, 1, 1)).reduced_until_year == 2026


def test_without_a_start_date_there_is_no_suggestion() -> None:
    assert retention(None, None, TODAY) == Retention(None, None, None)
    assert retention(None, FIFTEEN, TODAY) == Retention(None, None, None)


def test_choosing_7_without_a_start_date_asks_for_it() -> None:
    assert retention(None, SEVEN, TODAY).warning == WARNING_NO_START_DATE


@pytest.mark.parametrize(
    ("start", "warns"),
    [(date(2023, 12, 31), True), (date(2020, 1, 1), True), (date(2024, 12, 31), False), (date(2026, 1, 1), False)],
)
def test_choosing_7_outside_the_window_warns_but_never_blocks(start: date, warns: bool) -> None:
    result = retention(start, SEVEN, TODAY)
    assert (result.warning == WARNING_OUT_OF_PERIOD) is warns
    assert (result.warning is None) is not warns


@pytest.mark.parametrize("start", [None, date(2020, 1, 1), date(2023, 12, 31), date(2026, 1, 1)])
def test_choosing_15_never_warns(start: date | None) -> None:
    assert retention(start, FIFTEEN, TODAY).warning is None


def test_the_suggested_rate_is_a_string_with_two_decimals() -> None:
    assert retention(date(2026, 1, 1), None, TODAY).suggested_rate == "7.00"
    assert isinstance(retention(date(2026, 1, 1), None, TODAY).reduced_until_year, int)


@pytest.mark.parametrize("start", ["2025-01-15", 2025, True, 1.5])
def test_a_start_that_is_not_a_date_is_treated_as_missing(start: object) -> None:
    assert retention(start, SEVEN, TODAY) == Retention(None, None, WARNING_NO_START_DATE)
