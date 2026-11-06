"""AC-06 y AC-07 · Tipos de IVA, cuota, retención y total (SPEC-W-003 §5.1, D-03, ADR-0006)."""

import math
import random
from decimal import Decimal
from fractions import Fraction

import pytest

from cuadre.validators import TaxLine, Withholding
from cuadre.validators.vat import (
    MISSING_LINES,
    amounts_problem,
    lines_complete,
    parse_rate,
    percentage_of,
    rates_problem,
    sums,
    total_problem,
    withholding_problem,
)


def oracle(base_cents: int, rate: str) -> int:
    """`base × tipo / 100` con fracciones exactas y medio hacia arriba: nada de `Decimal` ni de `float`, para no probar el código con él mismo."""
    exact = Fraction(base_cents) * Fraction(Decimal(rate)) / 100
    return math.floor(exact + Fraction(1, 2))


# --- tipos -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("21", 21),
        ("21.00", 21),
        ("7.5", Decimal("7.5")),
        ("0", 0),
        ("100", 100),
        ("999.99", Decimal("999.99")),
        ("04", 4),
    ],
)
def test_parse_rate_accepts_numbers_with_up_to_three_integer_and_two_decimal_digits(
    text: str, value: int | Decimal
) -> None:
    assert parse_rate(text) == value


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "21,5",
        "1e1",
        "21.",
        ".5",
        "-5",
        "1000",
        "21.555",
        "２１",
        "21" + chr(10),
        " 21",
        "٢١",
        "21 ",
        "+21",
        "abc",
    ],
)
def test_parse_rate_rejects_everything_else(text: str | None) -> None:
    assert parse_rate(text) is None


# --- cálculo -----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "rate", "expected"),
    [
        (50, "21", 11),  # 10,50: el empate sube
        (115, "10", 12),  # 11,50
        (1, "50", 1),  # 0,50
        (435, "21", 91),  # 91,35
        (3333, "21", 700),  # 699,93
        (29, "21", 6),  # 6,09
        (2479, "21", 521),  # 520,59: la cuota de invoice_ok
        (3305, "21", 694),  # 694,05: la del ticket
        (12000, "21", 2520),
        (0, "21", 0),
        (100, "0", 0),
        (12345678901234, "21", 2592592569259),
    ],
)
def test_percentage_of_rounds_half_up(base: int, rate: str, expected: int) -> None:
    assert percentage_of(base, Decimal(rate)) == expected == oracle(base, rate)


def test_percentage_of_matches_an_independent_oracle_on_random_cases() -> None:
    rng = random.Random(20261106)
    rates = ["0", "4", "10", "21", "7.5", "5.5", "21.00", "16.5", "1.25", "99.99", "30", "2.1"]
    for _ in range(5000):
        base = rng.choice([rng.randint(0, 999), rng.randint(0, 10**6), rng.randint(0, 10**11)])
        rate = rng.choice(rates)
        assert percentage_of(base, Decimal(rate)) == oracle(base, rate), (base, rate)


# --- tipos permitidos --------------------------------------------------------------------------------------------------------------


def lines(*rates: str) -> tuple[TaxLine, ...]:
    return tuple(TaxLine(rate, 1000, percentage_of(1000, Decimal(rate))) for rate in rates)


@pytest.mark.parametrize("rate", ["0", "4", "10", "21", "21.00", "10.0", "04"])
def test_spanish_suppliers_may_use_zero_four_ten_and_twenty_one(rate: str) -> None:
    assert rates_problem(lines(rate), "national") is None


@pytest.mark.parametrize("rate", ["19", "7", "5", "5.5", "20", "22", "21.5", "100"])
def test_spanish_suppliers_may_not_use_any_other_rate(rate: str) -> None:
    assert "no es uno de los de España" in (rates_problem(lines(rate), "national") or "")


def test_an_unknown_scope_applies_the_spanish_rules() -> None:
    assert rates_problem(lines("21"), None) is None
    assert rates_problem(lines("19"), None) is not None


@pytest.mark.parametrize("rate", ["0", "19", "23", "27", "30", "30.00"])
def test_eu_suppliers_may_use_any_rate_up_to_thirty(rate: str) -> None:
    assert rates_problem(lines(rate), "eu") is None


@pytest.mark.parametrize("rate", ["30.01", "31", "100"])
def test_eu_suppliers_may_not_exceed_thirty(rate: str) -> None:
    assert "supera el 30 %" in (rates_problem(lines(rate), "eu") or "")


def test_the_problem_names_the_line_of_a_multi_line_invoice() -> None:
    assert "línea 2" in (rates_problem(lines("21", "19"), "national") or "")


def test_rates_need_complete_lines_and_a_readable_rate() -> None:
    assert rates_problem((), "national") == MISSING_LINES
    assert rates_problem((TaxLine(None, 100, 21),), "national") == MISSING_LINES
    assert "no es un número válido" in (rates_problem((TaxLine("abc", 100, 21),), "national") or "")


# --- cuota -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vat", "ok"), [(2520, True), (2519, True), (2521, True), (2518, False), (2522, False), (0, False), (25200, False)]
)
def test_the_vat_amount_may_differ_one_cent_from_the_rate(vat: int, ok: bool) -> None:
    assert (amounts_problem((TaxLine("21", 12000, vat),)) is None) is ok


@pytest.mark.parametrize(("vat", "ok"), [(11, True), (10, True), (12, True), (9, False), (13, False)])
def test_the_tolerance_applies_around_the_rounded_half_up_value(vat: int, ok: bool) -> None:
    assert (amounts_problem((TaxLine("21", 50, vat),)) is None) is ok  # 50 × 21 % = 10,50, que se redondea a 11


def test_every_line_is_checked_and_the_message_names_the_wrong_one() -> None:
    problem = amounts_problem((TaxLine("21", 10000, 2100), TaxLine("10", 5000, 600)))
    assert problem is not None and "línea 2" in problem
    assert "50,00 €" in problem and "5,00 €" in problem and "6,00 €" in problem


def test_amounts_need_complete_lines() -> None:
    assert amounts_problem(()) == MISSING_LINES
    assert amounts_problem((TaxLine("21", None, 21),)) == MISSING_LINES
    assert amounts_problem((TaxLine("abc", 100, 21),)) == MISSING_LINES


# --- retención ---------------------------------------------------------------------------------------------------------------------


TWO_LINES = (TaxLine("21", 10000, 2100), TaxLine("10", 5000, 500))


def test_no_withholding_is_not_checked() -> None:
    assert withholding_problem(None, TWO_LINES) is None


@pytest.mark.parametrize(
    ("amount", "ok"), [(2250, True), (2249, True), (2251, True), (2248, False), (2252, False), (1500, False)]
)
def test_the_withholding_is_the_rate_of_the_sum_of_all_the_bases(amount: int, ok: bool) -> None:
    """15 % de 150,00 € (las dos bases) son 22,50 €. 1.500 sería el 15 % de la primera base sola."""
    assert (withholding_problem(Withholding("15", amount), TWO_LINES) is None) is ok


def test_the_withholding_needs_its_rate_and_its_amount() -> None:
    assert "faltan el porcentaje o el importe" in (withholding_problem(Withholding(None, 100), TWO_LINES) or "")
    assert "faltan el porcentaje o el importe" in (withholding_problem(Withholding("15", None), TWO_LINES) or "")
    assert "no es un número válido" in (withholding_problem(Withholding("x", 100), TWO_LINES) or "")
    assert withholding_problem(Withholding("15", 100), ()) == MISSING_LINES


# --- total -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "ok"), [(14520, True), (14519, True), (14521, True), (14518, False), (14522, False), (14700, False)]
)
def test_the_total_may_differ_one_cent_from_the_sum(total: int, ok: bool) -> None:
    """El caso de US-005: 120,00 + 25,20 son 145,20, y 147,00 no cuadra."""
    assert (total_problem((TaxLine("21", 12000, 2520),), None, total) is None) is ok


def test_the_total_message_shows_both_figures() -> None:
    assert (
        total_problem((TaxLine("21", 12000, 2520),), None, 14700)
        == "Base más IVA da 145,20 € y el total indicado es 147,00 €."
    )


def test_the_total_subtracts_the_withholding() -> None:
    line = (TaxLine("21", 12000, 2520),)
    assert total_problem(line, Withholding("15", 1800), 12720) is None
    assert total_problem(line, Withholding("15", 1800), 14520) is not None  # sin restar la retención
    assert "Base más IVA menos retención" in (total_problem(line, Withholding("15", 1800), 14520) or "")


def test_the_total_adds_every_line() -> None:
    assert total_problem(TWO_LINES, None, 10000 + 2100 + 5000 + 500) is None
    assert total_problem(TWO_LINES, None, 12100) is not None  # solo la primera línea


def test_the_total_needs_complete_data() -> None:
    line = (TaxLine("21", 12000, 2520),)
    assert total_problem((), None, 100) == "No se puede comprobar: faltan datos."
    assert total_problem(line, None, None) == "No se puede comprobar: faltan datos."
    assert total_problem(line, Withholding("15", None), 14520) == "No se puede comprobar: falta el importe retenido."


def test_sums_and_completeness() -> None:
    assert sums(TWO_LINES) == (15000, 2600)
    assert lines_complete(TWO_LINES)
    assert not lines_complete(())
    assert not lines_complete((TaxLine("21", 1, None),))
