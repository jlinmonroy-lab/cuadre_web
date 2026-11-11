"""AC-01 a AC-14, AC-18, AC-22 y AC-23 · El modelo 130 de un trimestre, acumulado desde enero y casilla a casilla (SPEC-W-009 §5.1, RF-013, NFR-03 y NFR-08). Python puro."""

from datetime import date

import pytest

from cuadre.tax import (
    Box130,
    CostRow,
    IncomeRow,
    InvalidPeriod,
    Modelo130,
    PeriodInFuture,
    QuarterTooLarge,
    build_modelo_130,
    year_start,
)
from cuadre.tax.limits import NOTE_130_70, NOTE_130_DRAFT, NOTE_130_EXCLUSIONS, YEAR_MAX_DOCUMENTS

TODAY = date(2026, 6, 1)  # después de todos los trimestres de 2025
YEAR = 2025
MID_Q1 = date(2025, 2, 10)
CODES = ("01", "02", "03", "04", "05", "06", "07")


def income(id_: str, base: int, irpf: int = 0, *, day: date = MID_Q1, label: str | None = None) -> IncomeRow:
    return IncomeRow(id_, label or f"F-{id_}", day, base, irpf)


def cost(
    id_: str,
    base: int,
    vat: int = 0,
    *,
    deductible: bool = False,
    voided: bool = False,
    day: date = MID_Q1,
    label: str | None = None,
) -> CostRow:
    return CostRow(id_, label or f"Proveedor {id_}", day, base, vat, deductible, voided)


def build(
    incomes: list[IncomeRow] | None = None,
    costs: list[CostRow] | None = None,
    *,
    quarter: int = 1,
    year: int = YEAR,
    today: date = TODAY,
) -> Modelo130:
    return build_modelo_130(year, quarter, incomes or [], costs or [], today)


def box(model: Modelo130, code: str) -> Box130:
    return next(b for b in model.boxes if b.code == code)


def amounts(model: Modelo130) -> dict[str, int]:
    return {b.code: b.amount_cents for b in model.boxes}


# --- La forma -----------------------------------------------------------------------------------------------------------------------


def test_the_model_always_has_the_seven_boxes_in_order_with_their_groups() -> None:
    model = build()
    assert tuple(b.code for b in model.boxes) == CODES
    assert [b.group for b in model.boxes] == ["rendimiento"] * 4 + ["pagos"] * 2 + ["resultado"]
    assert all(b.amount_cents == 0 and b.items == () for b in model.boxes)


def test_the_period_runs_from_the_first_of_january_and_the_deadline_is_the_one_of_the_303() -> None:
    assert year_start(2025) == date(2025, 1, 1)
    model = build(quarter=2)
    assert (model.year, model.quarter) == (2025, 2)
    assert model.period_start == date(2025, 1, 1)  # acumulado: siempre desde enero
    assert model.period_end == date(2025, 7, 1)  # exclusivo
    assert model.deadline == date(2025, 7, 20)


@pytest.mark.parametrize(
    ("today", "status"),
    [
        (date(2025, 3, 31), "en_curso"),
        (date(2025, 4, 1), "plazo_abierto"),
        (date(2025, 4, 20), "plazo_abierto"),
        (date(2025, 4, 21), "plazo_cerrado"),
    ],
)
def test_the_deadline_status_follows_the_clock(today: date, status: str) -> None:  # AC-13
    assert build(today=today).deadline_status == status


# --- AC-01 a AC-04 · ingresos y gastos --------------------------------------------------------------------------------------------


def test_every_invoice_adds_its_base_to_box_01_and_is_an_item_of_it() -> None:  # AC-01
    model = build([income("a", 300_000, 45_000), income("b", 150_000), income("c", 80_000)])
    assert box(model, "01").amount_cents == 530_000
    assert [(i.kind, i.id, i.amount_cents) for i in box(model, "01").items] == [
        ("invoice", "a", 300_000),
        ("invoice", "b", 150_000),
        ("invoice", "c", 80_000),
    ]


def test_a_rectification_is_one_more_item_with_negative_amounts() -> None:  # AC-02
    model = build(
        [income("o", 300_000, 45_000), income("r", -50_000, -7_500, day=date(2025, 3, 5), label="R-2025-001")]
    )
    assert box(model, "01").amount_cents == 250_000
    assert [i.amount_cents for i in box(model, "01").items] == [300_000, -50_000]
    assert box(model, "06").amount_cents == 37_500


def test_a_cost_adds_its_base_plus_the_vat_that_is_not_deducted() -> None:  # AC-03
    model = build(
        costs=[
            cost("deducible", 40_000, 8_400, deductible=True),  # el IVA se deduce en el 303: aquí solo la base
            cost("no-deducible", 25_000, 5_250),  # base más IVA
            cost("sin-factura", 12_000),  # un gasto sin factura vale su importe
        ]
    )
    assert box(model, "02").amount_cents == 40_000 + (25_000 + 5_250) + 12_000
    assert {i.id: i.amount_cents for i in box(model, "02").items} == {
        "deducible": 40_000,
        "no-deducible": 30_250,
        "sin-factura": 12_000,
    }
    assert all(i.kind == "expense" for i in box(model, "02").items)


def test_a_voided_cost_neither_counts_nor_is_listed() -> None:  # AC-04
    model = build(costs=[cost("vivo", 10_000), cost("anulado", 99_999, 21_000, voided=True)])
    assert box(model, "02").amount_cents == 10_000
    assert [i.id for i in box(model, "02").items] == ["vivo"]


def test_the_vat_of_a_deductible_cost_never_counts_even_if_it_is_large() -> None:
    assert box(build(costs=[cost("a", 1_000, 99_999, deductible=True)]), "02").amount_cents == 1_000


# --- AC-05, AC-06 · rendimiento neto y el 20 % ------------------------------------------------------------------------------------


def test_the_net_yield_is_income_minus_costs_with_its_sign_and_the_twenty_percent_only_when_it_is_positive() -> (
    None
):  # AC-05
    positive = build([income("a", 100_000)], [cost("g", 30_000)])
    assert (box(positive, "03").amount_cents, box(positive, "04").amount_cents) == (70_000, 14_000)
    negative = build([income("a", 10_000)], [cost("g", 30_000)])
    assert (box(negative, "03").amount_cents, box(negative, "04").amount_cents) == (-20_000, 0)
    zero = build([income("a", 30_000)], [cost("g", 30_000)])
    assert (box(zero, "03").amount_cents, box(zero, "04").amount_cents) == (0, 0)


@pytest.mark.parametrize(
    ("net", "expected"),
    [(571_209, 114_242), (693_067, 138_613), (5, 1), (4, 1), (2, 0), (3, 1), (7, 1), (8, 2), (1, 0)],
)
def test_the_twenty_percent_rounds_half_up_to_the_cent(net: int, expected: int) -> None:  # AC-06
    # 20 % de 571209 = 114241,8 → 114242 (sube); de 693067 = 138613,4 → 138613 (baja); de 5 = 1 exacto; de 3 = 0,6 → 1; de 2 = 0,4 → 0.
    assert box(build([income("a", net)]), "04").amount_cents == expected


def test_the_twenty_percent_is_computed_once_on_box_03_not_added_up_per_document() -> None:  # AC-06, ADR-0006
    # Tres facturas de 12 céntimos: el 20 % de cada una (2,4) sale 2 y sumarían 6; el 20 % de 36 (7,2) es 7.
    model = build([income("a", 12), income("b", 12), income("c", 12)])
    assert box(model, "03").amount_cents == 36
    assert box(model, "04").amount_cents == 7


# --- AC-07 a AC-09 · acumulado, pagos anteriores y retenciones ---------------------------------------------------------------------


def test_the_second_quarter_includes_the_first_and_the_first_only_its_own() -> None:  # AC-07
    q1_doc = income("q1", 100_000, day=date(2025, 2, 1))
    q2_doc = income("q2", 50_000, day=date(2025, 5, 1))
    assert box(build([q1_doc, q2_doc], quarter=1), "01").amount_cents == 100_000
    second = build([q1_doc, q2_doc], quarter=2)
    assert box(second, "01").amount_cents == 150_000
    assert [i.id for i in box(second, "01").items] == ["q1", "q2"]


def test_the_previous_payments_are_the_max_of_zero_and_the_result_of_each_earlier_quarter() -> None:  # AC-08
    docs = [
        income("t1", 100_000, 15_000, day=date(2025, 2, 1)),  # T1: 20 % = 20.000; retención 15.000 → paga 5.000
        income("t2", 10_000, 0, day=date(2025, 5, 1)),  # T2 acumulado: 110.000 → 22.000 − 5.000 − 15.000 = 2.000
    ]
    third = build(docs, [cost("g", 400_000, day=date(2025, 8, 1))], quarter=3)  # T3: rendimiento muy negativo
    payments = {i.id: i.amount_cents for i in box(third, "05").items}
    assert payments == {"T1": 5_000, "T2": 2_000}  # los dos anteriores; el T3 aún no cuenta para sí mismo
    assert box(third, "05").amount_cents == 7_000
    fourth = build(docs, [cost("g", 400_000, day=date(2025, 8, 1))], quarter=4)
    assert {i.id: i.amount_cents for i in box(fourth, "05").items} == {
        "T1": 5_000,
        "T2": 2_000,
        "T3": 0,
    }  # un trimestre sin pago cuenta 0


def test_the_first_quarter_has_no_previous_payments() -> None:
    model = build([income("a", 100_000)])
    assert box(model, "05").amount_cents == 0 and box(model, "05").items == ()


def test_each_previous_quarter_is_an_item_with_its_label_and_the_last_day_of_that_quarter() -> None:
    fourth = build([income("a", 100_000, day=date(2025, 2, 1))], quarter=4)
    items = box(fourth, "05").items
    assert [(i.kind, i.id, i.label, i.date) for i in items] == [
        ("quarter", "T1", "T1 de 2025", date(2025, 3, 31)),
        ("quarter", "T2", "T2 de 2025", date(2025, 6, 30)),
        ("quarter", "T3", "T3 de 2025", date(2025, 9, 30)),
    ]


def test_the_withholding_is_the_sum_of_the_invoices_with_its_sign_and_only_those_with_withholding_are_listed() -> (
    None
):  # AC-09
    model = build(
        [
            income("con", 100_000, 15_000),
            income("sin", 50_000),
            income("devuelve", -20_000, -3_000, day=date(2025, 3, 1)),
        ]
    )
    assert box(model, "06").amount_cents == 12_000
    assert {i.id: i.amount_cents for i in box(model, "06").items} == {"con": 15_000, "devuelve": -3_000}


# --- AC-10 · el resultado ----------------------------------------------------------------------------------------------------------


def test_the_result_is_04_minus_05_minus_06_and_its_three_kinds() -> None:  # AC-10
    owed = build([income("a", 100_000)])  # 20 % = 20.000
    assert (owed.result_cents, owed.result_kind) == (20_000, "a_ingresar")
    retained = build([income("a", 100_000, 20_000)])  # 20.000 − 20.000
    assert (retained.result_cents, retained.result_kind) == (0, "nada_que_ingresar")  # cero con documentos
    over = build([income("a", 100_000, 30_000)])  # más retención que pago
    assert (over.result_cents, over.result_kind) == (-10_000, "nada_que_ingresar")  # un negativo no se arrastra
    empty = build()
    assert (empty.result_cents, empty.result_kind) == (0, "sin_actividad")


def test_a_period_with_only_voided_costs_is_without_activity_and_one_with_only_costs_is_not() -> None:
    assert build(costs=[cost("a", 5_000, voided=True)]).result_kind == "sin_actividad"
    only_costs = build(costs=[cost("a", 5_000)])
    assert only_costs.result_kind == "nada_que_ingresar" and box(only_costs, "03").amount_cents == -5_000


def test_the_derived_boxes_list_their_components_and_have_no_items() -> None:  # NFR-08
    model = build([income("a", 100_000, 5_000)], [cost("g", 10_000)])
    assert (box(model, "03").components, box(model, "04").components, box(model, "07").components) == (
        ("01", "02"),
        ("03",),
        ("04", "05", "06"),
    )
    for code in ("03", "04", "07"):
        assert box(model, code).items == ()
    got = amounts(model)
    assert got["03"] == got["01"] - got["02"] and got["07"] == got["04"] - got["05"] - got["06"]


# --- AC-12 · fronteras --------------------------------------------------------------------------------------------------------------


def test_the_documents_of_the_previous_year_and_of_the_next_do_not_count() -> None:  # AC-12
    docs = [
        income("viejo", 7_000, day=date(2024, 12, 31)),
        income("dentro", 1_000, day=date(2025, 1, 1)),
        income("nuevo", 9_000, day=date(2026, 1, 1)),
    ]
    first = build(docs)
    assert [i.id for i in box(first, "01").items] == ["dentro"]
    fourth = build(docs, quarter=4)
    assert [i.id for i in box(fourth, "01").items] == ["dentro"]
    new_year = build(docs, year=2026)
    assert [i.id for i in box(new_year, "01").items] == ["nuevo"]
    assert box(new_year, "05").amount_cents == 0


@pytest.mark.parametrize(
    ("day", "in_first", "in_second"),
    [
        (date(2025, 3, 31), True, True),
        (date(2025, 4, 1), False, True),
        (date(2025, 6, 30), False, True),
        (date(2025, 7, 1), False, False),
    ],
)
def test_the_first_and_last_day_of_each_quarter(day: date, in_first: bool, in_second: bool) -> None:  # AC-12
    docs = [income("a", 1_000, day=day)]
    assert bool(box(build(docs, quarter=1), "01").items) is in_first
    assert bool(box(build(docs, quarter=2), "01").items) is in_second


def test_a_cost_follows_the_same_borders_and_the_last_day_of_the_year_belongs_to_the_fourth_quarter() -> None:
    docs = [cost("a", 1_000, day=date(2025, 12, 31)), cost("b", 2_000, day=date(2026, 1, 1))]
    assert [i.id for i in box(build(costs=docs, quarter=4), "02").items] == ["a"]
    assert [i.id for i in box(build(costs=docs, quarter=1, year=2026), "02").items] == ["b"]


# --- AC-14 · el periodo -------------------------------------------------------------------------------------------------------------


def test_an_invalid_or_future_period_is_refused_before_looking_at_any_document() -> None:  # AC-14
    with pytest.raises(InvalidPeriod):
        build(quarter=5)
    with pytest.raises(InvalidPeriod):
        build(year=1999)
    with pytest.raises(PeriodInFuture):
        build(year=2026, quarter=4, today=date(2026, 9, 30))
    build(year=2026, quarter=3, today=date(2026, 9, 30))  # el trimestre en curso sí


# --- AC-18 · el límite de documentos -----------------------------------------------------------------------------------------------


def test_the_limit_counts_the_whole_period_so_far_invoices_and_costs_together() -> None:  # AC-18
    assert YEAR_MAX_DOCUMENTS == 10_000
    docs = [income(str(n), 100) for n in range(YEAR_MAX_DOCUMENTS)]
    assert len(box(build(docs), "01").items) == YEAR_MAX_DOCUMENTS  # justo en el límite pasa
    with pytest.raises(QuarterTooLarge) as error:
        build([*docs, income("extra", 100)])
    assert error.value.code == "quarter_too_large"
    mixed = [income(str(n), 100) for n in range(6_000)], [cost(str(n), 100) for n in range(4_000)]
    build(*mixed)  # 10.000 exactos
    with pytest.raises(QuarterTooLarge):
        build(mixed[0], [*mixed[1], cost("x", 100)])


def test_voided_costs_and_documents_outside_the_period_do_not_count_towards_the_limit() -> None:
    docs = [income(str(n), 100) for n in range(YEAR_MAX_DOCUMENTS)]
    noise = [income(f"o{n}", 100, day=date(2025, 8, 1)) for n in range(50)]  # del T3: fuera del T1
    voided = [cost(f"v{n}", 100, voided=True) for n in range(50)]
    build([*docs, *noise], voided)


# --- AC-23 · porcentaje con retención ----------------------------------------------------------------------------------------------


def test_the_withheld_share_is_the_base_with_withholding_over_box_01_rounded_to_the_integer() -> None:  # AC-23
    assert build([income("a", 100_000, 15_000), income("b", 100_000)]).withheld_share_percent == 50
    assert build([income("a", 423_459, 63_519), income("b", 230_000)]).withheld_share_percent == 65  # 64,80 sube
    assert build([income("a", 573_459, 86_019), income("b", 290_007)]).withheld_share_percent == 66  # 66,41 baja
    assert (
        build([income("a", 1, 1), income("b", 7)]).withheld_share_percent == 13
    )  # 12,5 exacto: medio hacia arriba, no al par
    assert build([income("a", 3, 1), income("b", 5)]).withheld_share_percent == 38  # 37,5 exacto: también sube
    assert build([income("a", 1, 0)]).withheld_share_percent == 0
    assert build([income("a", 1_000, 150)]).withheld_share_percent == 100


def test_the_share_is_none_when_box_01_is_not_positive_and_a_returned_withholding_subtracts_on_both_sides() -> (
    None
):  # AC-23
    assert build().withheld_share_percent is None
    assert (
        build([income("a", 10_000, 1_500), income("r", -10_000, -1_500, day=date(2025, 3, 1))]).withheld_share_percent
        is None
    )  # 01 = 0
    # Una rectificativa que devuelve retención resta de la base con retención y de la 01: 100.000 − 40.000 con retención sobre 100.000 − 40.000 + 40.000 sin ella.
    model = build(
        [income("a", 100_000, 15_000), income("r", -40_000, -6_000, day=date(2025, 3, 1)), income("s", 40_000)]
    )
    assert (box(model, "01").amount_cents, model.withheld_share_percent) == (100_000, 60)


# --- AC-22 · avisos ---------------------------------------------------------------------------------------------------------------


def test_the_fixed_notes_are_always_there_even_in_an_empty_period() -> None:  # AC-22
    for model in (build(), build([income("a", 100_000, 15_000)])):
        assert model.notes == (NOTE_130_DRAFT, NOTE_130_EXCLUSIONS, NOTE_130_70)
    assert "orientativo" in NOTE_130_DRAFT.lower() and "acumulados desde el 1 de enero" in NOTE_130_DRAFT
    for what in ("5 %", "minoraciones", "vivienda afecta", "compensación de resultados negativos"):
        assert what in NOTE_130_EXCLUSIONS
    assert "70 %" in NOTE_130_70 and "solo informativo" in NOTE_130_70


# --- Determinismo -------------------------------------------------------------------------------------------------------------------


def test_the_items_are_in_date_label_id_order_whatever_the_input_order() -> None:
    docs = [
        income("c", 100, day=date(2025, 2, 3), label="B"),
        income("a", 100, day=date(2025, 1, 3), label="Z"),
        income("b", 100, day=date(2025, 2, 3), label="A"),
        income("d", 100, day=date(2025, 2, 3), label="A"),
    ]
    assert [i.id for i in box(build(docs), "01").items] == ["a", "b", "d", "c"]
    assert [i.id for i in box(build(list(reversed(docs))), "01").items] == ["a", "b", "d", "c"]


def test_the_same_documents_in_any_order_give_the_same_model_and_the_input_is_not_changed() -> None:
    docs = [income(str(n), 1_000 + 37 * n, 150 * (n % 2), day=date(2025, 1 + n % 9, 1 + n)) for n in range(12)]
    spent = [cost(f"e{n}", 500 + n, 105 + n, deductible=n % 2 == 0, day=date(2025, 1 + n % 9, 2 + n)) for n in range(6)]
    before = (list(docs), list(spent))
    assert build(docs, spent, quarter=3) == build(list(reversed(docs)), list(reversed(spent)), quarter=3)
    assert (docs, spent) == before
