"""AC-05 · Fecha correcta y no futura (SPEC-W-003 §5.1)."""

from datetime import date

import pytest

from cuadre.validators import from_stored
from cuadre.validators.dates import issue_date_problem

TODAY = date(2026, 11, 6)


def problem(value: date | None, *, malformed: bool = False) -> str | None:
    return issue_date_problem(value, malformed=malformed, today=TODAY)


@pytest.mark.parametrize("value", [TODAY, date(2026, 11, 5), date(2026, 1, 1), date(2000, 1, 1), date(2024, 2, 29)])
def test_valid_dates_pass(value: date) -> None:
    assert problem(value) is None


def test_tomorrow_is_in_the_future() -> None:
    assert problem(date(2026, 11, 7)) == "La fecha es posterior a hoy."
    assert problem(date(2030, 1, 1)) == "La fecha es posterior a hoy."


def test_the_day_before_2000_is_too_old() -> None:
    assert problem(date(1999, 12, 31)) == "La fecha es anterior al 1 de enero de 2000."
    assert problem(date(1900, 1, 1)) == "La fecha es anterior al 1 de enero de 2000."


def test_a_missing_date_and_a_malformed_one_have_their_own_message() -> None:
    assert problem(None) == "Falta la fecha de la factura."
    assert problem(None, malformed=True) == "La fecha no es válida: revisa el día, el mes y el año."


@pytest.mark.parametrize(
    "text",
    [
        "2026-02-30",
        "2026-02-29",
        "2026-13-01",
        "2026-00-10",
        "2026-04-31",
        "2026/11/01",
        "1/1/2026",
        "20261101",
        "２０２６-11-01",
    ],
)
def test_texts_that_are_not_a_real_date_are_malformed(text: str) -> None:
    data = from_stored({"issue_date": text})
    assert data.issue_date is None and data.issue_date_malformed
    assert problem(data.issue_date, malformed=data.issue_date_malformed) is not None


def test_a_leap_day_is_a_real_date_only_in_a_leap_year() -> None:
    assert from_stored({"issue_date": "2024-02-29"}).issue_date == date(2024, 2, 29)
    assert from_stored({"issue_date": "2026-02-29"}).issue_date_malformed
