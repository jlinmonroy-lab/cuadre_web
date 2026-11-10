"""AC-07, AC-09 · Número visible, series rectificativas y orden de fechas (SPEC-W-007 §5.1.4, D-08, T7-03)."""

from datetime import date

import pytest

from cuadre.invoicing import display_number, is_out_of_order, is_reserved_series_code, rectifying_series_code


@pytest.mark.parametrize(
    ("code", "number", "expected"),
    [
        ("2026", 1, "2026-001"),
        ("2026", 9, "2026-009"),
        ("2026", 10, "2026-010"),
        ("2026", 14, "2026-014"),
        ("2026", 99, "2026-099"),
        ("2026", 100, "2026-100"),
        ("2026", 999, "2026-999"),
        ("2026", 1000, "2026-1000"),
        ("2026", 12345, "2026-12345"),
        ("2026", 999_999, "2026-999999"),
        ("R-2026", 1, "R-2026-001"),
        ("A-B", 7, "A-B-007"),
    ],
)
def test_ac_07_the_visible_number_has_three_digits_at_least(code, number, expected) -> None:
    assert display_number(code, number) == expected


@pytest.mark.parametrize("number", [0, -1, 1_000_000, 10**9, True, False, 1.0, "1", None])
def test_a_number_outside_one_to_999999_is_a_programming_error(number) -> None:
    with pytest.raises(ValueError):
        display_number("2026", number)  # type: ignore[arg-type]


def test_a_series_without_code_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        display_number("", 1)


@pytest.mark.parametrize(
    ("year", "expected"), [(2026, "R-2026"), (1999, "R-1999"), (2100, "R-2100"), (999, "R-0999"), (0, "R-0000")]
)
def test_the_rectifying_series_of_a_year(year, expected) -> None:
    assert rectifying_series_code(year) == expected


@pytest.mark.parametrize("year", [-1, 10_000, 99_999])
def test_a_year_that_does_not_fit_four_digits_is_a_programming_error(year) -> None:
    with pytest.raises(ValueError):
        rectifying_series_code(year)


@pytest.mark.parametrize("code", ["R-2026", "R-1999", "R-0000", "R-9999"])
def test_the_codes_r_year_are_reserved(code) -> None:
    assert is_reserved_series_code(code)


@pytest.mark.parametrize(
    "code",
    [
        "R-202",
        "R-20266",
        "R-2026 ",
        " R-2026",
        "r-2026",
        "R2026",
        "R-ABCD",
        "R-2026-1",
        "2026",
        "RECT",
        "",
        "R-٢٠٢٦",
        "AR-2026",
        "R-2026\n",
    ],
)
def test_other_codes_are_not_reserved(code) -> None:
    assert not is_reserved_series_code(code)


def test_ac_09_a_date_is_out_of_order_only_when_it_is_before_the_last_of_the_series() -> None:
    last = date(2026, 3, 10)
    assert is_out_of_order(date(2026, 3, 9), last)
    assert not is_out_of_order(date(2026, 3, 10), last)
    assert not is_out_of_order(date(2026, 3, 11), last)
    assert not is_out_of_order(date(2000, 1, 1), None)
