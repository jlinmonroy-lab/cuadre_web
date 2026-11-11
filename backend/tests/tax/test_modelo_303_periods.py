"""AC-09, AC-10, AC-11 · Trimestres naturales y plazos de presentación del modelo 303 (SPEC-W-008 §5.1, D-02). Python puro: las fechas son argumentos."""

from datetime import date

import pytest

from cuadre.tax import (
    InvalidPeriod,
    PeriodInFuture,
    deadline_status,
    filing_deadline,
    quarter_bounds,
    quarter_of,
    validate_period,
)

# --- AC-09 · el trimestre de una fecha ---------------------------------------------------------------------------------------------

QUARTER_OF = [
    (date(2025, 1, 1), (2025, 1)),
    (date(2025, 3, 31), (2025, 1)),
    (date(2025, 4, 1), (2025, 2)),
    (date(2025, 6, 30), (2025, 2)),
    (date(2025, 7, 1), (2025, 3)),
    (date(2025, 9, 30), (2025, 3)),
    (date(2025, 10, 1), (2025, 4)),
    (date(2025, 12, 31), (2025, 4)),
    (date(2026, 1, 1), (2026, 1)),
    (date(2024, 2, 29), (2024, 1)),  # bisiesto
]


@pytest.mark.parametrize(("day", "expected"), QUARTER_OF)
def test_a_date_belongs_to_its_natural_quarter(day: date, expected: tuple[int, int]) -> None:
    assert quarter_of(day) == expected


@pytest.mark.parametrize(
    ("year", "quarter", "start", "end"),
    [
        (2025, 1, date(2025, 1, 1), date(2025, 4, 1)),
        (2025, 2, date(2025, 4, 1), date(2025, 7, 1)),
        (2025, 3, date(2025, 7, 1), date(2025, 10, 1)),
        (2025, 4, date(2025, 10, 1), date(2026, 1, 1)),
        (2024, 1, date(2024, 1, 1), date(2024, 4, 1)),
        (9998, 4, date(9998, 10, 1), date(9999, 1, 1)),
    ],
)
def test_the_bounds_include_the_first_day_and_exclude_the_first_day_of_the_next_quarter(
    year: int, quarter: int, start: date, end: date
) -> None:
    assert quarter_bounds(year, quarter) == (start, end)


def test_every_day_of_a_year_falls_inside_the_bounds_of_its_own_quarter_and_of_no_other() -> None:
    day = date(2025, 1, 1)
    while day.year == 2025:
        year, quarter = quarter_of(day)
        for other in (1, 2, 3, 4):
            start, end = quarter_bounds(2025, other)
            assert (start <= day < end) == (other == quarter), day
        assert year == 2025
        day = date.fromordinal(day.toordinal() + 1)


# --- AC-10 · el plazo y su estado --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "quarter", "deadline"),
    [
        (2025, 1, date(2025, 4, 20)),
        (2025, 2, date(2025, 7, 20)),
        (2025, 3, date(2025, 10, 20)),
        (2025, 4, date(2026, 1, 30)),  # el cuarto se presenta en enero del año siguiente
        (2026, 4, date(2027, 1, 30)),
    ],
)
def test_the_filing_deadline_of_each_quarter(year: int, quarter: int, deadline: date) -> None:
    assert filing_deadline(year, quarter) == deadline


@pytest.mark.parametrize(
    ("today", "status"),
    [
        (date(2025, 1, 1), "en_curso"),  # el día que empieza
        (date(2025, 3, 31), "en_curso"),  # el último día del trimestre
        (date(2025, 4, 1), "plazo_abierto"),  # el primer día después
        (date(2025, 4, 20), "plazo_abierto"),  # el último día del plazo, incluido
        (date(2025, 4, 21), "plazo_cerrado"),
        (date(2026, 1, 1), "plazo_cerrado"),
    ],
)
def test_the_deadline_status_changes_on_the_days_that_matter(today: date, status: str) -> None:
    assert deadline_status(2025, 1, today) == status


def test_the_fourth_quarter_stays_open_through_january_of_the_next_year() -> None:
    assert deadline_status(2025, 4, date(2025, 12, 31)) == "en_curso"
    assert deadline_status(2025, 4, date(2026, 1, 1)) == "plazo_abierto"
    assert deadline_status(2025, 4, date(2026, 1, 30)) == "plazo_abierto"
    assert deadline_status(2025, 4, date(2026, 1, 31)) == "plazo_cerrado"


# --- AC-11 · periodo inválido o futuro ---------------------------------------------------------------------------------------------

TODAY = date(2026, 11, 11)


@pytest.mark.parametrize(
    ("year", "quarter"),
    [(2025, 0), (2025, 5), (2025, -1), (1999, 1), (9999, 1), (2000 - 1, 4), (10000, 1)],
)
def test_a_period_that_does_not_exist_is_invalid(year: int, quarter: int) -> None:
    with pytest.raises(InvalidPeriod) as error:
        validate_period(year, quarter, TODAY)
    assert error.value.code == "invalid_period"


@pytest.mark.parametrize(("year", "quarter"), [(True, 1), (2025, True), ("2025", 1), (2025, 1.0), (None, 1)])
def test_values_that_are_not_plain_integers_are_invalid(year: object, quarter: object) -> None:
    with pytest.raises(InvalidPeriod):
        validate_period(year, quarter, TODAY)  # type: ignore[arg-type]


def test_the_limits_of_the_years_are_valid() -> None:
    validate_period(2000, 1, TODAY)
    # El último año válido está en el futuro: no es inválido, es futuro.
    with pytest.raises(PeriodInFuture):
        validate_period(9998, 4, TODAY)


def test_a_quarter_that_has_not_started_is_in_the_future_and_the_current_one_is_not() -> None:
    validate_period(2026, 4, date(2026, 10, 1))  # el primer día del trimestre
    validate_period(2026, 4, date(2026, 11, 11))
    with pytest.raises(PeriodInFuture) as error:
        validate_period(2026, 4, date(2026, 9, 30))
    assert error.value.code == "period_in_future"
    with pytest.raises(PeriodInFuture):
        validate_period(2027, 1, date(2026, 12, 31))
    validate_period(2027, 1, date(2027, 1, 1))


def test_the_messages_say_what_is_wrong_without_echoing_what_was_sent() -> None:
    with pytest.raises(InvalidPeriod) as error:
        validate_period(1234, 7, TODAY)
    assert "1234" not in str(error.value)
    assert "7" not in str(error.value).replace("2000", "").replace("9998", "")
