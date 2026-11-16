"""AC-02, AC-03, AC-05, AC-06, AC-08 y AC-16 (parte pura) · Las reglas del reporte mensual (SPEC-W-013 §5.1). Python puro: sin base de datos."""

import inspect

import pytest

from cuadre.closing import CLOSING_MAX_DOCUMENTS, InvalidMonth, YearMonth
from cuadre.reports import (
    EXPENSES_NOTE,
    CategorisedExpense,
    MonthFigures,
    PeriodBeforeActivity,
    ReportTooLarge,
    build_comparison,
    expense_cost,
    expenses_note,
    group_by_category,
    quarter_of,
    scope_shares,
    share_bp,
    trend_window,
    variation_bp,
)
from cuadre.reports import rules as rules_module
from cuadre.validators.categories import LABELS, ExpenseCategory

C = ExpenseCategory


def exp(
    n: int, category: ExpenseCategory, base: int, vat: int = 0, deductible: bool = True, voided: bool = False
) -> CategorisedExpense:
    return CategorisedExpense(f"e{n:03d}", category, base, vat, deductible, voided)


def figures(year: int, month: int, total: int, expenses: int, status: str = "closed") -> MonthFigures:
    return MonthFigures(year, month, status, total, expenses)  # type: ignore[arg-type]


# --- Coste de un gasto ----------------------------------------------------------------------------------------------------------------


def test_a_deductible_vat_does_not_count_and_a_non_deductible_one_does() -> None:
    assert expense_cost(10_000, 2_100, True) == 10_000
    assert expense_cost(10_000, 2_100, False) == 12_100
    assert expense_cost(10_000, 0, False) == 10_000


@pytest.mark.parametrize("bad", [1.5, "100", None, True])
def test_amounts_must_be_real_integers(bad: object) -> None:
    with pytest.raises(TypeError):
        expense_cost(bad, 0, True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        expense_cost(0, bad, False)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        variation_bp(bad, 100)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        share_bp(100, bad)  # type: ignore[arg-type]


# --- Variación en puntos básicos (D-05, AC-03, AC-06) ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (120_000, 100_000, 2_000),  # +20 %
        (100_000, 100_000, 0),
        (50_000, 100_000, -5_000),  # −50 %
        (0, 100_000, -10_000),  # a cero: −100 %
        (1, 3, -6_667),  # 1/3 menos: −6 666,67 → −6 667
        (4, 3, 3_333),  # +1/3: 3 333,33 → 3 333
        (5, 3, 6_667),  # +2/3: 6 666,67 → 6 667
        (100_050, 100_000, 5),  # +0,05 % → 5 pb exactos
        (20_001, 20_000, 1),  # 0,5 pb exacto → sube a 1
        (19_999, 20_000, -1),  # −0,5 pb exacto → se aleja de cero: −1
        (200_001, 200_000, 0),  # 0,05 pb: no llega al medio
        (199_999, 200_000, 0),  # −0,05 pb: tampoco
        (2, 20_000, -9_999),  # −99,99 %
        (10**15 + 1, 10**15, 0),  # el 0,0000000000001 % no llega a 1 pb
    ],
)
def test_variation_rounds_half_up_on_the_absolute_value_with_its_sign(
    current: int, previous: int, expected: int
) -> None:
    assert variation_bp(current, previous) == expected


@pytest.mark.parametrize("previous", [0, -1, -100_000])
def test_there_is_no_variation_without_a_positive_reference(previous: int) -> None:
    assert variation_bp(120_000, previous) is None
    assert variation_bp(0, previous) is None


def test_a_negative_current_is_allowed_against_a_positive_reference() -> None:
    assert variation_bp(-50_000, 100_000) == -15_000  # una rectificativa grande: −150 %


# --- Cuotas por ámbito (D-06, AC-05) ----------------------------------------------------------------------------------------------------


def test_the_three_scopes_come_in_order_with_their_shares() -> None:
    shares = scope_shares(60_000, 30_000, 10_000)
    assert [(s.scope, s.base_cents, s.share_bp) for s in shares] == [
        ("national", 60_000, 6_000),
        ("eu", 30_000, 3_000),
        ("non_eu", 10_000, 1_000),
    ]


def test_a_scope_without_invoices_is_still_listed() -> None:
    shares = scope_shares(100_000, 0, 0)
    assert [s.scope for s in shares] == ["national", "eu", "non_eu"]
    assert [s.share_bp for s in shares] == [10_000, 0, 0]


def test_rounded_shares_may_not_add_up_to_exactly_a_hundred_percent() -> None:
    shares = scope_shares(1, 1, 1)
    assert [s.share_bp for s in shares] == [3_333, 3_333, 3_333]
    assert sum(s.share_bp or 0 for s in shares) == 9_999


@pytest.mark.parametrize("amounts", [(0, 0, 0), (-5_000, 0, 0), (10_000, 0, -10_000), (-1, -1, -1)])
def test_there_is_no_share_when_the_total_is_not_positive(amounts: tuple[int, int, int]) -> None:
    assert all(s.share_bp is None for s in scope_shares(*amounts))


def test_a_negative_scope_has_no_share_but_the_others_do() -> None:
    shares = scope_shares(120_000, -20_000, 0)
    assert [s.share_bp for s in shares] == [12_000, None, 0]  # el total es 100 000: la cuota puede pasar de 100 %


# --- Gastos por categoría (D-03, AC-02) ------------------------------------------------------------------------------------------------


def test_each_category_adds_base_and_non_deductible_vat_of_its_live_expenses() -> None:
    grouped = group_by_category(
        [
            exp(1, C.software, 10_000, 2_100, deductible=True),  # 10 000
            exp(2, C.software, 5_000, 1_050, deductible=False),  # 6 050
            exp(3, C.advisory, 30_000, 0),
            exp(4, C.software, 99_999, 21_000, deductible=False, voided=True),  # anulado: no cuenta
        ]
    )
    assert [(g.category, g.expenses_cents, g.expense_count) for g in grouped] == [
        (C.advisory, 30_000, 1),
        (C.software, 16_050, 2),
    ]


def test_labels_come_from_the_single_source() -> None:
    grouped = group_by_category([exp(n, category, 100 * (n + 1)) for n, category in enumerate(ExpenseCategory)])
    assert len(grouped) == 8
    assert {g.category: g.label for g in grouped} == dict(LABELS)


def test_order_is_by_amount_descending_and_then_by_label() -> None:
    grouped = group_by_category(
        [exp(1, C.supplies, 5_000), exp(2, C.software, 5_000), exp(3, C.other, 9_000), exp(4, C.advisory, 5_000)]
    )
    assert [g.category for g in grouped] == [
        C.other,
        C.advisory,
        C.supplies,
        C.software,
    ]  # Asesoría, Material, Software


def test_categories_with_nothing_to_show_do_not_come_out() -> None:
    grouped = group_by_category([exp(1, C.training, 0), exp(2, C.software, 4_000), exp(3, C.other, 0, 0, False)])
    assert [g.category for g in grouped] == [C.software]
    assert group_by_category([]) == ()
    assert group_by_category([exp(1, C.software, 100, voided=True)]) == ()


def test_a_category_that_does_not_exist_is_an_error_not_other() -> None:
    bad = CategorisedExpense("e001", "inventada", 100, 0, True, False)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        group_by_category([bad])


def test_a_category_given_as_its_text_value_is_understood() -> None:
    as_text = CategorisedExpense("e001", "software", 700, 0, True, False)  # type: ignore[arg-type]
    assert [(g.category, g.expenses_cents) for g in group_by_category([as_text])] == [(C.software, 700)]


def test_too_many_expenses_fail_instead_of_being_silently_cut() -> None:
    at_limit = [exp(n, C.other, 1) for n in range(CLOSING_MAX_DOCUMENTS)]
    assert group_by_category(at_limit)[0].expenses_cents == CLOSING_MAX_DOCUMENTS
    with pytest.raises(ReportTooLarge) as caught:
        group_by_category([*at_limit, exp(0, C.other, 1)])
    assert caught.value.code == "report_too_large"


# --- Aviso de descuadre (D-04, AC-10) ---------------------------------------------------------------------------------------------------


def test_the_note_only_appears_when_the_figures_differ() -> None:
    assert expenses_note(12_345, 12_345) is None
    assert expenses_note(0, 0) is None
    assert expenses_note(12_345, 12_000) == EXPENSES_NOTE
    assert expenses_note(0, 1) == EXPENSES_NOTE


def test_the_note_carries_no_amounts() -> None:
    assert not any(ch.isdigit() for ch in EXPENSES_NOTE)


# --- Ventana de la tendencia (D-07, AC-08) ---------------------------------------------------------------------------------------------


def test_twelve_months_ending_at_the_selected_one_across_a_year_boundary() -> None:
    window = trend_window(YearMonth(2026, 3), YearMonth(2024, 1))
    assert len(window) == 12
    assert window[0] == YearMonth(2025, 4) and window[-1] == YearMonth(2026, 3)
    assert window == tuple(sorted(window))


def test_the_window_does_not_go_before_the_first_active_month() -> None:
    window = trend_window(YearMonth(2026, 9), YearMonth(2026, 5))
    assert window == (
        YearMonth(2026, 5),
        YearMonth(2026, 6),
        YearMonth(2026, 7),
        YearMonth(2026, 8),
        YearMonth(2026, 9),
    )


def test_the_first_active_month_alone_is_a_window_of_one() -> None:
    assert trend_window(YearMonth(2026, 5), YearMonth(2026, 5)) == (YearMonth(2026, 5),)


def test_exactly_twelve_months_of_history_gives_twelve() -> None:
    assert len(trend_window(YearMonth(2026, 12), YearMonth(2026, 1))) == 12
    assert len(trend_window(YearMonth(2026, 12), YearMonth(2025, 12))) == 12
    assert len(trend_window(YearMonth(2026, 12), YearMonth(2025, 11))) == 12


def test_without_a_first_month_only_the_selected_one_is_shown() -> None:
    assert trend_window(YearMonth(2026, 9), None) == (YearMonth(2026, 9),)


def test_a_month_before_the_first_activity_is_not_shown() -> None:
    with pytest.raises(PeriodBeforeActivity) as caught:
        trend_window(YearMonth(2026, 4), YearMonth(2026, 5))
    assert caught.value.code == "closing_not_found"


@pytest.mark.parametrize("months", [0, -1, 121, True])
def test_the_length_of_the_window_is_bounded(months: int) -> None:
    with pytest.raises(ValueError):
        trend_window(YearMonth(2026, 9), YearMonth(2020, 1), months)


def test_a_shorter_window_can_be_asked_for() -> None:
    assert trend_window(YearMonth(2026, 9), YearMonth(2020, 1), 3) == (
        YearMonth(2026, 7),
        YearMonth(2026, 8),
        YearMonth(2026, 9),
    )


# --- Comparación con el mes anterior (D-05, AC-03, AC-04) -------------------------------------------------------------------------------


def test_the_comparison_carries_amounts_deltas_and_variations() -> None:
    comparison = build_comparison(figures(2026, 9, 120_000, 40_000), figures(2026, 8, 100_000, 50_000, "pending"))
    assert comparison is not None
    assert (comparison.previous_year, comparison.previous_month, comparison.previous_status) == (2026, 8, "pending")
    assert (comparison.total_cents, comparison.expenses_cents, comparison.result_cents) == (100_000, 50_000, 50_000)
    assert (comparison.total_delta_cents, comparison.expenses_delta_cents, comparison.result_delta_cents) == (
        20_000,
        -10_000,
        30_000,
    )
    assert (comparison.total_variation_bp, comparison.expenses_variation_bp) == (2_000, -2_000)


def test_without_a_previous_month_there_is_no_comparison() -> None:
    assert build_comparison(figures(2026, 5, 100, 0), None) is None


def test_a_previous_month_without_a_reference_keeps_the_deltas_but_not_the_variations() -> None:
    comparison = build_comparison(figures(2026, 9, 50_000, 0), figures(2026, 8, 0, 0))
    assert comparison is not None
    assert comparison.total_delta_cents == 50_000
    assert comparison.total_variation_bp is None and comparison.expenses_variation_bp is None


def test_the_comparison_crosses_the_year_boundary_with_what_the_service_gives() -> None:
    comparison = build_comparison(figures(2027, 1, 10_000, 1_000), figures(2026, 12, 8_000, 2_000))
    assert comparison is not None and (comparison.previous_year, comparison.previous_month) == (2026, 12)
    assert comparison.result_delta_cents == (10_000 - 1_000) - (8_000 - 2_000)


# --- Trimestre -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("month", "quarter"), [(1, 1), (3, 1), (4, 2), (6, 2), (7, 3), (9, 3), (10, 4), (12, 4)])
def test_the_quarter_of_a_month(month: int, quarter: int) -> None:
    assert quarter_of(month) == quarter


@pytest.mark.parametrize("month", [0, 13, -1, True, 1.5])
def test_a_month_that_does_not_exist_has_no_quarter(month: object) -> None:
    with pytest.raises(InvalidMonth):
        quarter_of(month)  # type: ignore[arg-type]


# --- RES-02 ------------------------------------------------------------------------------------------------------------------------------


def test_the_module_never_uses_decimals() -> None:
    source = inspect.getsource(rules_module)
    assert "float" not in source and "Decimal" not in source and "locale" not in source and "round(" not in source
