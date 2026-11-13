"""AC-01, AC-02, AC-07, AC-14 (parte pura) y AC-20 · El cálculo de un mes (SPEC-W-012 §5.1, D-02, D-06). Python puro: sin base de datos."""

import inspect
from datetime import date
from typing import Any

import pytest

from cuadre.closing import (
    CLOSING_MAX_DOCUMENTS,
    ClosingTooLarge,
    InvalidMonth,
    MonthExpense,
    MonthInvoice,
    YearMonth,
    build_month,
    build_months,
    payload_of,
)
from cuadre.closing import rules as rules_module

NORTE = "11111111-1111-4111-8111-111111111111"
KREATIV = "22222222-2222-4222-8222-222222222222"
ACME = "33333333-3333-4333-8333-333333333333"


def inv(
    n: int,
    day: date,
    base: int,
    client: str = NORTE,
    *,
    name: str = "Estudio Norte S.L.",
    scope: str = "national",
    kind: str = "standard",
) -> MonthInvoice:
    return MonthInvoice(f"i{n:03d}", day, kind, base, client, name, scope)  # type: ignore[arg-type]


def exp(n: int, day: date, base: int, vat: int = 0, *, deductible: bool = False, voided: bool = False) -> MonthExpense:
    return MonthExpense(f"e{n:03d}", day, base, vat, deductible, voided)


SEP = (2026, 9)


def september(invoices: list[MonthInvoice], expenses: list[MonthExpense] | None = None):  # noqa: ANN201
    return build_month(*SEP, invoices, expenses or [])


# --- AC-01 · Los totales por ámbito, por cliente y los gastos ----------------------------------------------------------------------------


def test_the_story_month_has_its_totals_by_scope_client_and_expenses() -> None:
    invoices = [
        inv(1, date(2026, 9, 3), 150_000),
        inv(2, date(2026, 9, 10), 50_000, KREATIV, name="Kreativ GmbH", scope="eu"),
        inv(3, date(2026, 9, 20), 20_000, ACME, name="Acme Inc.", scope="non_eu"),
        inv(4, date(2026, 9, 25), 30_000),
    ]
    expenses = [exp(1, date(2026, 9, 5), 10_000, 2_100, deductible=True), exp(2, date(2026, 9, 6), 29_400)]
    month = september(invoices, expenses)
    assert (month.year, month.month, month.invoice_count) == (2026, 9, 4)
    assert (month.national_cents, month.eu_cents, month.non_eu_cents, month.total_cents) == (
        180_000,
        50_000,
        20_000,
        250_000,
    )
    assert month.expenses_cents == 10_000 + 29_400  # el IVA deducible no cuenta como coste
    assert [(c.client_id, c.name, c.scope, c.base_cents, c.invoice_count) for c in month.by_client] == [
        (NORTE, "Estudio Norte S.L.", "national", 180_000, 2),
        (KREATIV, "Kreativ GmbH", "eu", 50_000, 1),
        (ACME, "Acme Inc.", "non_eu", 20_000, 1),
    ]


def test_a_month_with_no_documents_closes_at_zero() -> None:
    month = september([], [])
    assert (month.invoice_count, month.total_cents, month.expenses_cents, month.by_client) == (0, 0, 0, ())
    assert payload_of(month)["by_client"] == []


def test_only_the_documents_of_the_month_count() -> None:
    invoices = [
        inv(1, date(2026, 8, 31), 111),
        inv(2, date(2026, 9, 1), 1_000),
        inv(3, date(2026, 9, 30), 2_000),
        inv(4, date(2026, 10, 1), 222),
        inv(5, date(2025, 9, 15), 333),
    ]
    expenses = [
        exp(1, date(2026, 8, 31), 5),
        exp(2, date(2026, 9, 1), 10),
        exp(3, date(2026, 9, 30), 20),
        exp(4, date(2026, 10, 1), 7),
    ]
    month = september(invoices, expenses)
    assert (month.total_cents, month.invoice_count, month.expenses_cents) == (3_000, 2, 30)


@pytest.mark.parametrize(
    ("year", "month", "day"),
    [
        (2026, 12, date(2026, 12, 31)),
        (2027, 1, date(2027, 1, 1)),
        (2024, 2, date(2024, 2, 29)),
        (2026, 2, date(2026, 2, 28)),
    ],
)
def test_month_edges_belong_to_their_month(year: int, month: int, day: date) -> None:
    here = build_month(year, month, [inv(1, day, 700)], [exp(1, day, 5)])
    assert (here.total_cents, here.expenses_cents) == (700, 5)
    other = YearMonth(year, month).next()
    elsewhere = build_months([inv(1, day, 700)], [exp(1, day, 5)], [other])[0]
    assert (elsewhere.total_cents, elsewhere.expenses_cents) == (0, 0)


def test_several_months_are_built_in_the_requested_order() -> None:
    invoices = [inv(1, date(2026, 9, 3), 100), inv(2, date(2026, 8, 3), 200)]
    months = build_months(invoices, [], [YearMonth(2026, 9), YearMonth(2026, 8), YearMonth(2026, 7)])
    assert [(m.month, m.total_cents) for m in months] == [(9, 100), (8, 200), (7, 0)]


# --- AC-07 · Rectificativas ---------------------------------------------------------------------------------------------------------------


def test_a_rectification_counts_its_difference_in_its_own_month() -> None:
    original = inv(1, date(2026, 8, 20), 100_000)
    rectification = inv(2, date(2026, 9, 5), -40_000, kind="rectifying")
    august, september_ = build_months([original, rectification], [], [YearMonth(2026, 8), YearMonth(2026, 9)])
    assert (august.total_cents, august.invoice_count) == (100_000, 1)  # el mes de la original no cambia
    assert (september_.total_cents, september_.invoice_count) == (-40_000, 0)  # no cuenta como factura emitida
    assert [(c.client_id, c.base_cents, c.invoice_count) for c in september_.by_client] == [(NORTE, -40_000, 0)]


def test_a_rectification_keeps_the_scope_and_client_of_its_invoice() -> None:
    kreativ = dict(client=KREATIV, name="Kreativ GmbH", scope="eu")
    invoices = [
        inv(1, date(2026, 9, 2), 90_000, **kreativ),
        inv(2, date(2026, 9, 9), -90_000, kind="rectifying", **kreativ),
    ]  # type: ignore[arg-type]
    month = september(invoices)
    assert (month.eu_cents, month.total_cents, month.invoice_count) == (0, 0, 1)
    assert [(c.base_cents, c.invoice_count) for c in month.by_client] == [(0, 1)]  # el cliente sigue en el desglose


# --- Gastos -------------------------------------------------------------------------------------------------------------------------------


def test_expenses_are_the_base_plus_the_vat_that_cannot_be_deducted() -> None:
    expenses = [
        exp(1, date(2026, 9, 1), 10_000, 2_100, deductible=True),  # solo la base
        exp(2, date(2026, 9, 2), 10_000, 2_100, deductible=False),  # base + IVA
        exp(3, date(2026, 9, 3), 29_400),  # manual, sin IVA
        exp(4, date(2026, 9, 4), 99_999, 21_000, deductible=False, voided=True),  # anulado: no cuenta
    ]
    assert september([], expenses).expenses_cents == 10_000 + 12_100 + 29_400


# --- Nombre, ámbito y orden del desglose --------------------------------------------------------------------------------------------------


def test_the_name_is_the_one_of_the_latest_invoice_of_the_client() -> None:
    invoices = [
        inv(2, date(2026, 9, 20), 100, name="Estudio Norte, S.L."),
        inv(1, date(2026, 9, 2), 100, name="Estudio Norte S.L."),
    ]
    assert [c.name for c in september(invoices).by_client] == ["Estudio Norte, S.L."]
    same_day = [inv(1, date(2026, 9, 2), 100, name="A"), inv(2, date(2026, 9, 2), 100, name="B")]
    assert [c.name for c in september(same_day).by_client] == ["B"]  # el desempate es el id de la factura


def test_a_client_that_changed_scope_in_the_month_appears_once_per_scope() -> None:
    invoices = [
        inv(1, date(2026, 9, 2), 1_000, scope="national"),
        inv(2, date(2026, 9, 9), 4_000, scope="eu"),
    ]
    month = september(invoices)
    assert (month.national_cents, month.eu_cents) == (1_000, 4_000)
    assert [(c.scope, c.base_cents) for c in month.by_client] == [("eu", 4_000), ("national", 1_000)]
    assert (
        sum(c.base_cents for c in month.by_client if c.scope == "eu") == month.eu_cents
    )  # lo que exige la base de datos


def test_the_breakdown_is_ordered_by_amount_then_name_then_id() -> None:
    invoices = [
        inv(1, date(2026, 9, 1), 500, "ccc00000-0000-4000-8000-000000000000", name="Zeta"),
        inv(2, date(2026, 9, 1), 500, "bbb00000-0000-4000-8000-000000000000", name="Alfa"),
        inv(3, date(2026, 9, 1), 500, "aaa00000-0000-4000-8000-000000000000", name="Alfa"),
        inv(4, date(2026, 9, 1), 900, NORTE, name="Mayor"),
        inv(5, date(2026, 9, 1), -50, KREATIV, name="Negativo"),
    ]
    assert [(c.name, c.client_id[:3]) for c in september(invoices).by_client] == [
        ("Mayor", "111"),
        ("Alfa", "aaa"),
        ("Alfa", "bbb"),
        ("Zeta", "ccc"),
        ("Negativo", "222"),
    ]


def test_the_result_does_not_depend_on_the_order_of_the_input() -> None:
    invoices = [inv(n, date(2026, 9, 1 + n % 28), 100 * n, [NORTE, KREATIV, ACME][n % 3]) for n in range(1, 40)]
    expenses = [exp(n, date(2026, 9, 1 + n % 28), 10 * n, n, deductible=n % 2 == 0) for n in range(1, 20)]
    forward = september(invoices, expenses)
    assert september(list(reversed(invoices)), list(reversed(expenses))) == forward


# --- La foto que se guarda --------------------------------------------------------------------------------------------------------------


def test_the_payload_is_exactly_what_the_database_function_expects() -> None:
    month = september(
        [inv(1, date(2026, 9, 1), 100), inv(2, date(2026, 9, 2), 50, KREATIV, name="K", scope="eu")],
        [exp(1, date(2026, 9, 3), 7)],
    )
    payload = payload_of(month)
    assert list(payload) == [
        "invoice_count",
        "national_cents",
        "eu_cents",
        "non_eu_cents",
        "total_cents",
        "expenses_cents",
        "by_client",
    ]
    assert all(type(payload[k]) is int for k in list(payload)[:-1])
    assert payload["by_client"] == [
        {"client_id": NORTE, "name": "Estudio Norte S.L.", "scope": "national", "base_cents": 100, "invoice_count": 1},
        {"client_id": KREATIV, "name": "K", "scope": "eu", "base_cents": 50, "invoice_count": 1},
    ]


# --- AC-20 · Sin decimales ni entradas dudosas -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [12.5, 100.0, "100", None, True])
def test_an_amount_that_is_not_a_whole_number_is_refused(bad: Any) -> None:
    with pytest.raises(TypeError):
        september([inv(1, date(2026, 9, 1), bad)])
    with pytest.raises(TypeError):
        september([], [exp(1, date(2026, 9, 1), bad)])
    with pytest.raises(TypeError):
        september([], [exp(1, date(2026, 9, 1), 100, bad)])


def test_an_unknown_scope_or_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="Ámbito"):
        september([inv(1, date(2026, 9, 1), 1, scope="mars")])
    with pytest.raises(ValueError, match="Tipo"):
        september([inv(1, date(2026, 9, 1), 1, kind="proforma")])


@pytest.mark.parametrize(("year", "month"), [(1999, 9), (2026, 0), (2026, 13), (10000, 1), (True, 9)])
def test_a_month_that_does_not_exist_is_refused(year: Any, month: int) -> None:
    with pytest.raises(InvalidMonth) as caught:
        build_month(year, month, [], [])
    assert caught.value.code == "invalid_period"


def test_too_many_documents_fail_instead_of_being_silently_cut() -> None:
    day = date(2026, 9, 1)
    at_limit = [inv(n, day, 1) for n in range(CLOSING_MAX_DOCUMENTS)]
    assert september(at_limit).invoice_count == CLOSING_MAX_DOCUMENTS
    with pytest.raises(ClosingTooLarge) as caught:
        september(at_limit, [exp(1, day, 1)])
    assert caught.value.code == "closing_too_large"


def test_the_module_never_uses_decimals() -> None:
    source = inspect.getsource(rules_module)
    assert "float" not in source and "Decimal" not in source and "locale" not in source and "round(" not in source
