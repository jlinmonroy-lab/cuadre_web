"""AC-11 y AC-14 · Propiedades del cierre con documentos generados al azar (semilla fija, SPEC-W-012 §5.1).

Para cualquier conjunto de documentos: el total es la suma de los ámbitos y del desglose por cliente, las facturas del desglose suman las ordinarias del mes, el
orden de entrada no importa, un documento de otro mes no cambia nada, los meses de un año suman lo que suma el año calculado aparte y los de un trimestre
cuadran con la casilla 01 y los gastos del modelo 130. Los oráculos usan solo enteros y no importan el código del cierre.
"""

import random
from datetime import date, timedelta

from cuadre.closing import MonthExpense, MonthInvoice, YearMonth, build_month, build_months
from cuadre.tax import CostRow, IncomeRow, build_modelo_130

YEAR = 2025
TODAY = date(2026, 6, 1)
RUNS = 300
CLIENTS = [
    ("11111111-1111-4111-8111-111111111111", "Estudio Norte S.L.", "national"),
    ("22222222-2222-4222-8222-222222222222", "Kreativ GmbH", "eu"),
    ("33333333-3333-4333-8333-333333333333", "Acme Inc.", "non_eu"),
    ("44444444-4444-4444-8444-444444444444", "Café Liebre S.L.", "national"),
    ("55555555-5555-4555-8555-555555555555", "Café Liebre S.L.", "eu"),  # mismo nombre, otro cliente
]
SCOPES = ("national", "eu", "non_eu")


def day_in(rng: random.Random, year: int = YEAR) -> date:
    return date(year, 1, 1) + timedelta(days=rng.randrange(0, 365))


def random_invoice(rng: random.Random, n: int, year: int = YEAR) -> MonthInvoice:
    client_id, name, scope = rng.choice(CLIENTS)
    if rng.random() < 0.15:  # el cliente cambió de ámbito
        scope = rng.choice(SCOPES)
    kind = "rectifying" if rng.random() < 0.2 else "standard"
    base = rng.choice([1, 50, 999, 12_345, 250_000, 1_000_000]) * (
        -1 if kind == "rectifying" else rng.choice([1, 1, 1, -1])
    )
    return MonthInvoice(f"i{n:04d}", day_in(rng, year), kind, base, client_id, name, scope)  # type: ignore[arg-type]


def random_expense(rng: random.Random, n: int, year: int = YEAR) -> MonthExpense:
    base = rng.choice([100, 2_500, 80_000, 900_000])
    vat = rng.choice([0, base * 21 // 100])
    return MonthExpense(f"e{n:04d}", day_in(rng, year), base, vat, vat > 0 and rng.random() < 0.5, rng.random() < 0.1)


def random_docs(rng: random.Random, count: int = 30) -> tuple[list[MonthInvoice], list[MonthExpense]]:
    return (
        [random_invoice(rng, n) for n in range(rng.randrange(0, count))],
        [random_expense(rng, n) for n in range(rng.randrange(0, count))],
    )


def test_totals_and_breakdown_always_add_up() -> None:
    rng = random.Random(1201)
    for _ in range(RUNS):
        invoices, expenses = random_docs(rng)
        for month in range(1, 13):
            built = build_month(YEAR, month, invoices, expenses)
            mine = [i for i in invoices if i.issue_date.month == month]
            assert built.total_cents == sum(i.base_cents for i in mine)
            assert built.total_cents == built.national_cents + built.eu_cents + built.non_eu_cents
            assert built.total_cents == sum(c.base_cents for c in built.by_client)
            assert (
                built.invoice_count
                == sum(1 for i in mine if i.kind == "standard")
                == sum(c.invoice_count for c in built.by_client)
            )
            for scope, cents in zip(SCOPES, (built.national_cents, built.eu_cents, built.non_eu_cents), strict=True):
                assert cents == sum(
                    c.base_cents for c in built.by_client if c.scope == scope
                )  # lo que exige la base de datos
            assert built.expenses_cents == sum(
                e.base_cents + (0 if e.deductible_vat else e.vat_cents)
                for e in expenses
                if e.expense_date.month == month and not e.voided
            )
            assert len({(c.client_id, c.scope) for c in built.by_client}) == len(built.by_client)


def test_the_order_of_the_input_does_not_change_the_result() -> None:
    rng = random.Random(1202)
    for _ in range(RUNS):
        invoices, expenses = random_docs(rng)
        month = rng.randrange(1, 13)
        expected = build_month(YEAR, month, invoices, expenses)
        rng.shuffle(invoices)
        rng.shuffle(expenses)
        assert build_month(YEAR, month, invoices, expenses) == expected


def test_a_document_of_another_month_changes_nothing() -> None:
    rng = random.Random(1203)
    for _ in range(RUNS):
        invoices, expenses = random_docs(rng)
        month = rng.randrange(1, 13)
        expected = build_month(YEAR, month, invoices, expenses)
        outside_invoice = random_invoice(rng, 9000, year=YEAR + 1)
        outside_expense = random_expense(rng, 9000, year=YEAR - 1)
        assert build_month(YEAR, month, [*invoices, outside_invoice], [*expenses, outside_expense]) == expected


def test_building_many_months_at_once_equals_building_them_one_by_one() -> None:
    rng = random.Random(1204)
    for _ in range(RUNS):
        invoices, expenses = random_docs(rng)
        months = [YearMonth(YEAR, m) for m in rng.sample(range(1, 13), rng.randrange(1, 13))]
        together = build_months(invoices, expenses, months)
        assert together == [build_month(m.year, m.month, invoices, expenses) for m in months]


def test_the_twelve_months_add_up_to_the_year() -> None:
    rng = random.Random(1205)
    for _ in range(RUNS):
        invoices, expenses = random_docs(rng)
        months = build_months(invoices, expenses, [YearMonth(YEAR, m) for m in range(1, 13)])
        assert sum(m.total_cents for m in months) == sum(i.base_cents for i in invoices)
        assert sum(m.invoice_count for m in months) == sum(1 for i in invoices if i.kind == "standard")
        assert sum(m.expenses_cents for m in months) == sum(
            e.base_cents + (0 if e.deductible_vat else e.vat_cents) for e in expenses if not e.voided
        )


def test_the_months_of_a_quarter_match_the_modelo_130() -> None:
    """AC-11: la suma de los meses de enero al fin de cada trimestre es la casilla 01 (ingresos) y los gastos del 130; ambos calculados con otro código."""
    rng = random.Random(1206)
    for _ in range(RUNS):
        invoices, expenses = random_docs(rng)
        incomes = [IncomeRow(i.id, i.id, i.issue_date, i.base_cents, 0) for i in invoices]
        costs = [
            CostRow(e.id, e.id, e.expense_date, e.base_cents, e.vat_cents, e.deductible_vat, e.voided) for e in expenses
        ]
        months = build_months(invoices, expenses, [YearMonth(YEAR, m) for m in range(1, 13)])
        for quarter in range(1, 5):
            boxes = {b.code: b.amount_cents for b in build_modelo_130(YEAR, quarter, incomes, costs, TODAY).boxes}
            upto = months[: 3 * quarter]
            assert sum(m.total_cents for m in upto) == boxes["01"]
            assert sum(m.expenses_cents for m in upto) == boxes["02"]
