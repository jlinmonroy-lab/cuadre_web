"""AC-08, AC-09 · Propiedades del modelo 303 con documentos generados al azar (semilla fija, SPEC-W-008 NFR-08 y T8-04).

Para cualquier conjunto de documentos: la suma de los items de cada casilla es la casilla, las derivadas son sus fórmulas, el orden de entrada no
importa, partir los documentos en dos grupos y sumar sus casillas da las del conjunto, y un documento de otro trimestre no cambia nada.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from cuadre.tax import ExpenseLine, ExpenseRow, InvoiceRow, Modelo303, build_modelo_303

TODAY = date(2026, 6, 1)
YEAR, QUARTER = 2025, 3
START = date(2025, 7, 1)
RUNS = 300
DOC_CODES = ("01", "03", "04", "06", "07", "09", "28", "29", "59", "120")
ALL_CODES = ("01", "03", "04", "06", "07", "09", "27", "28", "29", "45", "46", "59", "120")


def vat_of(base: int, rate: int) -> int:
    sign = -1 if base < 0 else 1
    return sign * ((abs(base) * rate * 2 + 100) // 200)


def random_day(rng: random.Random, *, inside: bool = True) -> date:
    if inside:
        return START + timedelta(days=rng.randrange(0, 92))  # julio, agosto y septiembre
    return rng.choice(
        [START - timedelta(days=rng.randrange(1, 400)), date(2025, 10, 1) + timedelta(days=rng.randrange(0, 200))]
    )


def random_invoice(rng: random.Random, n: int, *, inside: bool = True) -> InvoiceRow:
    treatment = rng.choice(
        [
            "national_vat",
            "national_vat",
            "eu_consumer_vat",
            "non_eu_consumer_vat",
            "eu_reverse_charge",
            "non_eu_not_subject",
        ]
    )
    base = rng.choice([1, 5, 50, 105, 999, 12_345, 250_000, 1_000_000]) * rng.choice([1, 1, 1, -1])
    if treatment in ("eu_reverse_charge", "non_eu_not_subject"):
        rate, vat = 0, 0
    else:
        rate = rng.choice([4, 10, 21])
        vat = vat_of(base, rate)
    return InvoiceRow(f"i{n}", f"F{n:04d}", random_day(rng, inside=inside), treatment, Decimal(rate), base, vat)  # type: ignore[arg-type]


def random_expense(rng: random.Random, n: int, *, inside: bool = True) -> ExpenseRow:
    lines = tuple(
        ExpenseLine(Decimal(rate), base, vat_of(base, rate))
        for rate in rng.sample([0, 4, 10, 21], rng.randrange(0, 4))
        for base in [rng.choice([100, 2_500, 80_000])]
    )
    return ExpenseRow(
        f"e{n}", f"P{n:04d}", random_day(rng, inside=inside), rng.random() < 0.7, rng.random() < 0.1, lines
    )


def random_documents(rng: random.Random, count: int) -> tuple[list[InvoiceRow], list[ExpenseRow]]:
    invoices = [random_invoice(rng, n) for n in range(rng.randrange(0, count))]
    expenses = [random_expense(rng, n) for n in range(rng.randrange(0, count))]
    return invoices, expenses


def build(invoices: list[InvoiceRow], expenses: list[ExpenseRow]) -> Modelo303:
    return build_modelo_303(YEAR, QUARTER, invoices, expenses, TODAY)


def amounts(model: Modelo303) -> dict[str, int]:
    return {b.code: b.amount_cents for b in model.boxes}


def test_the_sum_of_the_items_of_each_box_is_the_box_and_the_derived_ones_follow_their_formulas() -> (
    None
):  # NFR-08, T8-04
    rng = random.Random(303)
    for _ in range(RUNS):
        model = build(*random_documents(rng, 25))
        got = amounts(model)
        assert tuple(got) == ALL_CODES
        for b in model.boxes:
            if b.measure is None:
                assert b.items == ()
                continue
            assert sum(i.base_cents if b.measure == "base" else i.vat_cents for i in b.items) == b.amount_cents
        assert got["27"] == got["03"] + got["06"] + got["09"]
        assert got["45"] == got["29"]
        assert got["46"] == got["27"] - got["45"] == model.result_cents
        kind = model.result_kind
        assert kind != "a_ingresar" or got["46"] > 0
        assert kind != "a_compensar" or got["46"] < 0
        assert kind != "a_cero" or got["46"] == 0
        assert kind != "sin_actividad" or (got["46"] == 0 and not any(b.items for b in model.boxes))


def test_every_invoice_of_the_quarter_is_in_exactly_the_boxes_that_its_treatment_dictates() -> None:
    rng = random.Random(7)
    for _ in range(RUNS):
        invoices, _spent = random_documents(rng, 25)
        model = build(invoices, [])
        listed = {b.code: {i.id for i in b.items} for b in model.boxes}
        for invoice in invoices:
            places = {code for code in DOC_CODES if invoice.id in listed[code]}
            if invoice.tax_treatment == "eu_reverse_charge":
                assert places == {"59"}
            elif invoice.tax_treatment == "non_eu_not_subject":
                assert places == {"120"}
            else:
                base_box, vat_box = {4: ("01", "03"), 10: ("04", "06"), 21: ("07", "09")}[int(invoice.vat_rate)]
                assert places == {base_box, vat_box}


def test_the_order_of_the_documents_does_not_change_the_model() -> None:
    rng = random.Random(11)
    for _ in range(RUNS):
        invoices, expenses = random_documents(rng, 25)
        shuffled_i, shuffled_e = list(invoices), list(expenses)
        rng.shuffle(shuffled_i)
        rng.shuffle(shuffled_e)
        assert build(invoices, expenses) == build(shuffled_i, shuffled_e)


def test_splitting_the_documents_in_two_groups_adds_up_to_the_whole() -> None:  # aditividad
    rng = random.Random(13)
    for _ in range(RUNS):
        invoices, expenses = random_documents(rng, 25)
        cut_i, cut_e = rng.randrange(0, len(invoices) + 1), rng.randrange(0, len(expenses) + 1)
        whole = amounts(build(invoices, expenses))
        first = amounts(build(invoices[:cut_i], expenses[:cut_e]))
        second = amounts(build(invoices[cut_i:], expenses[cut_e:]))
        assert whole == {code: first[code] + second[code] for code in ALL_CODES}


def test_documents_of_other_quarters_do_not_change_anything() -> None:  # AC-09
    rng = random.Random(17)
    for _ in range(RUNS):
        invoices, expenses = random_documents(rng, 20)
        noise_i = [random_invoice(rng, 1_000 + n, inside=False) for n in range(rng.randrange(0, 10))]
        noise_e = [random_expense(rng, 1_000 + n, inside=False) for n in range(rng.randrange(0, 10))]
        assert build(invoices + noise_i, expenses + noise_e) == build(invoices, expenses)


def test_the_boxes_of_the_four_quarters_of_a_year_add_up_to_the_boxes_of_the_whole_year_by_construction() -> None:
    rng = random.Random(19)
    for _ in range(100):
        invoices = [
            InvoiceRow(
                f"i{n}",
                f"F{n}",
                date(2025, 1, 1) + timedelta(days=rng.randrange(0, 365)),
                "national_vat",
                Decimal(21),
                b,
                vat_of(b, 21),
            )
            for n, b in enumerate(rng.choice([105, 250, 12_345, 99_999]) for _ in range(30))
        ]
        total_base = sum(
            sum(i.base_cents for i in build_modelo_303(2025, q, invoices, [], TODAY).boxes[4].items)
            for q in (1, 2, 3, 4)
        )
        assert total_base == sum(i.base_cents for i in invoices)  # cada factura cae en un trimestre y en uno solo
