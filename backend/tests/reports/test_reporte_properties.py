"""AC-02, AC-03, AC-05 y AC-06 · Propiedades de las reglas del reporte con datos al azar (semilla fija, SPEC-W-013 §5.1).

Para cualquier conjunto de gastos: las categorías suman lo mismo que los gastos del cierre del mes (la misma regla en las dos partes), el orden de entrada no
importa y un gasto anulado no cambia nada. Para cualquier par de importes: la variación y las cuotas coinciden con un oráculo exacto (`Fraction`) redondeado
*half-up* sobre el valor absoluto. Los oráculos usan solo enteros y no importan el código bajo prueba.
"""

import random
from datetime import date
from fractions import Fraction
from math import floor

from cuadre.closing import MonthExpense, build_month
from cuadre.reports import CategorisedExpense, group_by_category, scope_shares, share_bp, variation_bp
from cuadre.validators.categories import ExpenseCategory

RUNS = 400
CATEGORIES = list(ExpenseCategory)
DAY = date(2026, 9, 15)


def random_expense(rng: random.Random, n: int) -> CategorisedExpense:
    base = rng.choice([0, 1, 100, 2_500, 80_000, 900_000])
    vat = rng.choice([0, base * 21 // 100])
    return CategorisedExpense(
        f"e{n:04d}", rng.choice(CATEGORIES), base, vat, vat > 0 and rng.random() < 0.5, rng.random() < 0.15
    )


def random_expenses(rng: random.Random, count: int = 40) -> list[CategorisedExpense]:
    return [random_expense(rng, n) for n in range(rng.randrange(0, count))]


def as_closing_expenses(expenses: list[CategorisedExpense]) -> list[MonthExpense]:
    return [MonthExpense(e.id, DAY, e.base_cents, e.vat_cents, e.deductible_vat, e.voided) for e in expenses]


def half_up_abs(value: Fraction) -> int:
    """El oráculo: el entero más cercano, con el medio hacia fuera de cero, calculado con fracciones exactas."""
    magnitude = floor(abs(value) + Fraction(1, 2))
    return -magnitude if value < 0 else magnitude


def test_the_categories_add_up_to_the_expenses_of_the_closing() -> None:
    rng = random.Random(1301)
    for _ in range(RUNS):
        expenses = random_expenses(rng)
        closing = build_month(2026, 9, [], as_closing_expenses(expenses))
        grouped = group_by_category(expenses)
        assert sum(g.expenses_cents for g in grouped) == closing.expenses_cents
        assert sum(g.expense_count for g in grouped) <= sum(1 for e in expenses if not e.voided)


def test_the_order_of_the_input_does_not_matter() -> None:
    rng = random.Random(1302)
    for _ in range(RUNS):
        expenses = random_expenses(rng)
        shuffled = expenses[:]
        rng.shuffle(shuffled)
        assert group_by_category(shuffled) == group_by_category(expenses)


def test_a_voided_expense_changes_nothing_and_the_result_is_ordered_without_empty_categories() -> None:
    rng = random.Random(1303)
    for _ in range(RUNS):
        expenses = random_expenses(rng)
        extra = CategorisedExpense("zzz", rng.choice(CATEGORIES), 123_456, 25_925, False, True)
        grouped = group_by_category(expenses)
        assert group_by_category([*expenses, extra]) == grouped
        assert all(g.expenses_cents != 0 for g in grouped)
        assert [(-g.expenses_cents, g.label) for g in grouped] == sorted((-g.expenses_cents, g.label) for g in grouped)
        assert len({g.category for g in grouped}) == len(grouped)


def test_variation_is_the_exact_ratio_rounded_half_up() -> None:
    rng = random.Random(1304)
    for _ in range(RUNS * 5):
        previous = rng.choice([1, 3, 7, 99, 100, 12_345, 1_000_000, 10**12 + 7])
        current = rng.randrange(-previous, previous * 5)
        exact = Fraction((current - previous) * 10_000, previous)
        assert variation_bp(current, previous) == half_up_abs(exact)
        assert variation_bp(current, -previous) is None
        assert variation_bp(current, 0) is None


def test_a_zero_change_is_zero_basis_points_and_swapping_the_sign_swaps_the_result() -> None:
    rng = random.Random(1305)
    for _ in range(RUNS):
        base = rng.randrange(1, 10**9)
        assert variation_bp(base, base) == 0
        up = variation_bp(base + rng.randrange(0, base), base)
        assert up is not None and up >= 0
        down = variation_bp(base - rng.randrange(0, base), base)
        assert down is not None and down <= 0


def test_each_share_is_within_one_basis_point_of_the_exact_one() -> None:
    rng = random.Random(1306)
    for _ in range(RUNS * 3):
        national, eu, non_eu = (rng.choice([0, 1, 999, 12_345, 250_000, 10**9]) for _ in range(3))
        total = national + eu + non_eu
        shares = scope_shares(national, eu, non_eu)
        assert [s.scope for s in shares] == ["national", "eu", "non_eu"]
        assert [s.base_cents for s in shares] == [national, eu, non_eu]
        for s in shares:
            if total <= 0:
                assert s.share_bp is None
            else:
                assert (
                    s.share_bp == half_up_abs(Fraction(s.base_cents * 10_000, total)) == share_bp(s.base_cents, total)
                )
        if total > 0:
            assert abs(sum(s.share_bp or 0 for s in shares) - 10_000) <= 2  # tres redondeos de medio punto como mucho
