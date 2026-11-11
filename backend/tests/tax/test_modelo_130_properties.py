"""AC-07, AC-08, AC-11, AC-12 · Propiedades del modelo 130 con documentos generados al azar (semilla fija, SPEC-W-009 NFR-08 y T9-04).

Para cualquier conjunto de documentos: la suma de los items de cada casilla es la casilla, las derivadas son sus fórmulas, la 05 de un trimestre es la suma de lo
que pagaron los anteriores calculados por separado, nada posterior al fin del trimestre cambia el resultado, las casillas lineales son aditivas, el orden de
entrada no importa y un documento de otro año no cambia nada. Los oráculos usan solo enteros y no importan el código del 130.
"""

import random
from datetime import date, timedelta
from fractions import Fraction
from math import floor

from cuadre.tax import CostRow, IncomeRow, Modelo130, build_modelo_130, quarter_bounds

TODAY = date(2026, 6, 1)
YEAR = 2025
RUNS = 300
CODES = ("01", "02", "03", "04", "05", "06", "07")


def day_in(rng: random.Random, year: int = YEAR) -> date:
    return date(year, 1, 1) + timedelta(days=rng.randrange(0, 365))


def random_income(rng: random.Random, n: int, year: int = YEAR) -> IncomeRow:
    base = rng.choice([1, 5, 12, 50, 999, 12_345, 250_000, 1_000_000]) * rng.choice([1, 1, 1, -1])
    irpf = 0 if rng.random() < 0.4 else (abs(base) * 15 + 50) // 100 * (1 if base > 0 else -1)
    return IncomeRow(f"i{n}", f"F{n:04d}", day_in(rng, year), base, irpf)


def random_cost(rng: random.Random, n: int, year: int = YEAR) -> CostRow:
    base = rng.choice([100, 2_500, 80_000, 900_000])
    return CostRow(
        f"e{n}", f"P{n:04d}", day_in(rng, year), base, base * 21 // 100, rng.random() < 0.5, rng.random() < 0.1
    )


def random_docs(rng: random.Random, count: int = 25) -> tuple[list[IncomeRow], list[CostRow]]:
    return (
        [random_income(rng, n) for n in range(rng.randrange(0, count))],
        [random_cost(rng, n) for n in range(rng.randrange(0, count))],
    )


def build(incomes: list[IncomeRow], costs: list[CostRow], quarter: int = 4) -> Modelo130:
    return build_modelo_130(YEAR, quarter, incomes, costs, TODAY)


def amounts(model: Modelo130) -> dict[str, int]:
    return {b.code: b.amount_cents for b in model.boxes}


def twenty_percent(cents: int) -> int:
    """El 20 % de un importe positivo, medio hacia arriba, con solo enteros."""
    return (cents * 40 + 100) // 200


def test_the_sum_of_the_items_of_each_box_is_the_box_and_the_derived_ones_follow_their_formulas() -> (
    None
):  # NFR-08, T9-04
    rng = random.Random(130)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng)
        model = build(incomes, costs, rng.randrange(1, 5))
        got = amounts(model)
        assert tuple(got) == CODES
        for box in model.boxes:
            if box.code in ("03", "04", "07"):
                assert box.items == ()
            else:
                assert sum(item.amount_cents for item in box.items) == box.amount_cents, box.code
        assert got["03"] == got["01"] - got["02"]
        assert got["04"] == (twenty_percent(got["03"]) if got["03"] > 0 else 0)
        assert got["07"] == got["04"] - got["05"] - got["06"] == model.result_cents
        kind = model.result_kind
        assert kind != "a_ingresar" or got["07"] > 0
        assert kind != "nada_que_ingresar" or got["07"] <= 0
        # «Sin actividad»: ningún documento (la 05 sí lista los trimestres anteriores, con pago 0, a partir del T2).
        documents = [b for b in model.boxes if b.code in ("01", "02", "06")]
        assert kind != "sin_actividad" or (not any(b.items for b in documents) and got["07"] == 0)


def test_box_05_of_a_quarter_is_the_sum_of_what_the_earlier_quarters_paid_computed_on_their_own() -> None:  # AC-08
    rng = random.Random(8)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng)
        for quarter in (2, 3, 4):
            model = build(incomes, costs, quarter)
            earlier = [build(incomes, costs, k) for k in range(1, quarter)]
            paid = [max(0, e.result_cents) for e in earlier]
            assert amounts(model)["05"] == sum(paid)
            five = next(b for b in model.boxes if b.code == "05")
            assert [item.amount_cents for item in five.items] == paid
            assert [item.id for item in five.items] == [f"T{k}" for k in range(1, quarter)]


def test_nothing_after_the_end_of_the_quarter_changes_the_result() -> None:  # AC-07, AC-12
    rng = random.Random(7)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng)
        quarter = rng.randrange(1, 4)
        _, end = quarter_bounds(YEAR, quarter)
        kept_incomes = [i for i in incomes if i.issue_date < end]
        kept_costs = [c for c in costs if c.expense_date < end]
        assert build(incomes, costs, quarter) == build(kept_incomes, kept_costs, quarter)


def test_the_linear_boxes_are_additive_when_the_documents_are_split_in_two() -> None:
    rng = random.Random(13)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng)
        cut_i, cut_c = rng.randrange(0, len(incomes) + 1), rng.randrange(0, len(costs) + 1)
        quarter = rng.randrange(1, 5)
        whole = amounts(build(incomes, costs, quarter))
        first = amounts(build(incomes[:cut_i], costs[:cut_c], quarter))
        second = amounts(build(incomes[cut_i:], costs[cut_c:], quarter))
        for code in ("01", "02", "06"):
            assert whole[code] == first[code] + second[code], code


def test_the_order_of_the_documents_does_not_change_the_model() -> None:
    rng = random.Random(11)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng)
        shuffled_i, shuffled_c = list(incomes), list(costs)
        rng.shuffle(shuffled_i)
        rng.shuffle(shuffled_c)
        quarter = rng.randrange(1, 5)
        assert build(incomes, costs, quarter) == build(shuffled_i, shuffled_c, quarter)


def test_documents_of_another_year_do_not_change_anything() -> None:  # AC-12
    rng = random.Random(17)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng, 20)
        noise_i = [random_income(rng, 1_000 + n, rng.choice([2024, 2026])) for n in range(rng.randrange(0, 10))]
        noise_c = [random_cost(rng, 1_000 + n, rng.choice([2024, 2026])) for n in range(rng.randrange(0, 10))]
        quarter = rng.randrange(1, 5)
        assert build(incomes + noise_i, costs + noise_c, quarter) == build(incomes, costs, quarter)


def test_the_withheld_share_follows_an_integer_only_oracle() -> None:  # AC-23
    rng = random.Random(23)
    for _ in range(RUNS):
        incomes, costs = random_docs(rng)
        model = build(incomes, costs, 4)
        in_year = [i for i in incomes if i.issue_date.year == YEAR]
        total = sum(i.base_cents for i in in_year)
        if total <= 0:
            assert model.withheld_share_percent is None
            continue
        withheld = sum(i.base_cents for i in in_year if i.irpf_cents != 0)
        expected = floor(Fraction(withheld * 100, total) + Fraction(1, 2))
        assert model.withheld_share_percent == expected
