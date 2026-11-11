"""AC-01 a AC-08, AC-12, AC-16 y AC-21 · El modelo 303 de un trimestre, casilla a casilla (SPEC-W-008 §5.1, RF-013, NFR-03 y NFR-08). Python puro."""

from datetime import date
from decimal import Decimal

import pytest

from cuadre.tax import (
    Box,
    ExpenseLine,
    ExpenseRow,
    InvalidPeriod,
    InvoiceRow,
    Modelo303,
    PeriodInFuture,
    QuarterTooLarge,
    UnsupportedVatRate,
    build_modelo_303,
)
from cuadre.tax.limits import (
    NOTE_303_349,
    NOTE_303_CANARIAS,
    NOTE_303_DRAFT,
    NOTE_303_EXCLUSIONS,
    QUARTER_MAX_DOCUMENTS,
)

TODAY = date(2026, 1, 15)  # después de todos los trimestres de 2025
YEAR, QUARTER = 2025, 2  # abril-junio de 2025
IN_Q = date(2025, 5, 10)
ALL_CODES = ("01", "03", "04", "06", "07", "09", "27", "28", "29", "45", "46", "59", "120")


def invoice(
    id_: str,
    base: int,
    rate: int | str = 21,
    *,
    vat: int | None = None,
    day: date = IN_Q,
    treatment: str = "national_vat",
    label: str | None = None,
) -> InvoiceRow:
    """Una factura; si no se da la cuota se calcula como `base × tipo / 100` redondeado medio hacia arriba (solo enteros, base ≥ 0)."""
    rate_d = Decimal(rate)
    if vat is None:
        vat = (base * int(rate_d) * 2 + 100) // 200
    return InvoiceRow(id_, label or f"F-{id_}", day, treatment, rate_d, base, vat)  # type: ignore[arg-type]


def expense(
    id_: str,
    lines: list[tuple[int | str, int, int]],
    *,
    day: date = IN_Q,
    deductible: bool = True,
    voided: bool = False,
    label: str | None = None,
) -> ExpenseRow:
    return ExpenseRow(
        id_,
        label or f"Proveedor {id_}",
        day,
        deductible,
        voided,
        tuple(ExpenseLine(Decimal(r), b, v) for r, b, v in lines),
    )


def build(
    invoices: list[InvoiceRow] | None = None, expenses: list[ExpenseRow] | None = None, **kw: object
) -> Modelo303:
    return build_modelo_303(
        kw.get("year", YEAR), kw.get("quarter", QUARTER), invoices or [], expenses or [], kw.get("today", TODAY)
    )  # type: ignore[arg-type]


def box(model: Modelo303, code: str) -> Box:
    return next(b for b in model.boxes if b.code == code)


def amounts(model: Modelo303) -> dict[str, int]:
    return {b.code: b.amount_cents for b in model.boxes}


# --- La forma: siempre las trece casillas, en el orden de la pantalla -------------------------------------------------------------


def test_the_model_always_has_the_thirteen_boxes_in_screen_order() -> None:
    model = build()
    assert tuple(b.code for b in model.boxes) == ALL_CODES
    assert all(b.amount_cents == 0 and b.items == () for b in model.boxes)


def test_the_period_data_comes_from_the_domain() -> None:
    model = build()
    assert (model.year, model.quarter) == (2025, 2)
    assert model.period_start == date(2025, 4, 1)
    assert model.period_end == date(2025, 7, 1)  # exclusivo
    assert model.deadline == date(2025, 7, 20)
    assert model.deadline_status == "plazo_cerrado"
    assert build(today=date(2025, 6, 30)).deadline_status == "en_curso"
    assert build(today=date(2025, 7, 20)).deadline_status == "plazo_abierto"


# --- AC-01 · facturas nacionales por tipo ------------------------------------------------------------------------------------------


def test_national_invoices_add_up_in_the_boxes_of_their_rate() -> None:  # AC-01
    model = build([invoice("a", 120_000, 21), invoice("b", 50_000, 10), invoice("c", 25_000, 4)])
    got = amounts(model)
    assert (got["07"], got["09"]) == (120_000, 25_200)
    assert (got["04"], got["06"]) == (50_000, 5_000)
    assert (got["01"], got["03"]) == (25_000, 1_000)
    assert got["27"] == 25_200 + 5_000 + 1_000  # la 27 es la suma de las tres cuotas
    assert got["59"] == got["120"] == 0


def test_every_invoice_is_an_item_of_its_base_box_and_of_its_vat_box() -> None:
    model = build([invoice("a", 100_000, 21, label="2025-001")])
    for code in ("07", "09"):
        (item,) = box(model, code).items
        assert (item.kind, item.id, item.label, item.date) == ("invoice", "a", "2025-001", IN_Q)
        assert (item.base_cents, item.vat_cents) == (100_000, 21_000)


def test_the_vat_of_each_document_is_added_as_is_without_rounding_the_sum_again() -> None:  # D-05
    # 105 al 10 % → 11 por documento (10,5 → 11); dos documentos suman 22, no 21 (que saldría de 2,1 sobre 210).
    model = build([invoice("a", 105, 10), invoice("b", 105, 10)])
    assert (box(model, "04").amount_cents, box(model, "06").amount_cents) == (210, 22)


def test_a_rate_written_with_decimals_is_the_same_rate() -> None:
    model = build([invoice("a", 100_000, "21.00"), invoice("b", 10_000, "10.00"), invoice("c", 10_000, "4.00")])
    assert (box(model, "07").amount_cents, box(model, "04").amount_cents, box(model, "01").amount_cents) == (
        100_000,
        10_000,
        10_000,
    )


# --- AC-02 · UE y fuera de la UE ---------------------------------------------------------------------------------------------------


def test_the_eu_company_goes_to_59_and_the_non_eu_not_subject_to_120_and_neither_adds_to_27() -> None:  # AC-02
    model = build(
        [
            invoice("a", 150_000, 0, vat=0, treatment="eu_reverse_charge"),
            invoice("b", 90_000, 0, vat=0, treatment="non_eu_not_subject"),
            invoice("c", 10_000, 21),
        ]
    )
    got = amounts(model)
    assert got["59"] == 150_000
    assert got["120"] == 90_000
    assert got["27"] == 2_100  # solo la nacional
    assert [i.id for i in box(model, "59").items] == ["a"]
    assert [i.id for i in box(model, "120").items] == ["b"]
    assert box(model, "59").items[0].vat_cents == 0


# --- AC-03 · particulares con IVA español -----------------------------------------------------------------------------------------


def test_consumers_with_spanish_vat_add_up_in_the_box_of_their_rate_like_national_invoices() -> None:  # AC-03
    model = build(
        [
            invoice("a", 5_050, 21, treatment="eu_consumer_vat"),  # 1.060,5 → 1.061
            invoice("b", 3_333, 10, treatment="non_eu_consumer_vat"),  # 333,3 → 333
        ]
    )
    got = amounts(model)
    assert (got["07"], got["09"]) == (5_050, 1_061)
    assert (got["04"], got["06"]) == (3_333, 333)
    assert got["59"] == got["120"] == 0


# --- AC-04 · rectificativas --------------------------------------------------------------------------------------------------------


def test_a_rectification_is_one_more_item_with_negative_amounts_in_its_own_quarter() -> None:  # AC-04
    original = invoice("o", 120_000, 21, day=date(2025, 1, 20))  # T1
    rectification = invoice("r", -20_000, 21, vat=-4_200, day=date(2025, 5, 4), label="R-2025-001")  # T2
    t1 = build([original, rectification], quarter=1)
    t2 = build([original, rectification], quarter=2)
    assert (box(t1, "07").amount_cents, box(t1, "09").amount_cents) == (120_000, 25_200)
    assert (box(t2, "07").amount_cents, box(t2, "09").amount_cents) == (-20_000, -4_200)
    (item,) = box(t2, "07").items
    assert (item.id, item.label, item.base_cents, item.vat_cents) == ("r", "R-2025-001", -20_000, -4_200)


def test_a_rectification_of_an_eu_invoice_subtracts_from_59() -> None:
    model = build([invoice("r", -50_000, 0, vat=0, treatment="eu_reverse_charge")])
    assert box(model, "59").amount_cents == -50_000
    assert NOTE_303_349 in model.notes  # distinto de cero, también negativo


def test_an_invoice_and_its_total_annulment_in_the_same_quarter_net_to_zero_but_the_quarter_has_activity() -> None:
    model = build([invoice("o", 120_000, 21), invoice("r", -120_000, 21, vat=-25_200)])
    assert amounts(model)["09"] == 0 and amounts(model)["07"] == 0
    assert model.result_kind == "a_cero"
    assert len(box(model, "07").items) == 2


# --- AC-05, AC-06 · gastos ---------------------------------------------------------------------------------------------------------


def test_deductible_expenses_add_to_28_and_29_and_the_45_is_the_29() -> None:  # AC-05
    model = build(expenses=[expense("a", [(21, 40_000, 8_400)]), expense("b", [(10, 5_000, 500)])])
    got = amounts(model)
    assert (got["28"], got["29"], got["45"]) == (45_000, 8_900, 8_900)
    assert [i.id for i in box(model, "28").items] == ["a", "b"]
    assert box(model, "45").items == ()


def test_expenses_without_deductible_vat_and_voided_ones_do_not_count() -> None:  # AC-05
    model = build(
        expenses=[
            expense("ok", [(21, 10_000, 2_100)]),
            expense("no", [(21, 20_000, 4_200)], deductible=False),
            expense("void", [(21, 30_000, 6_300)], voided=True),
        ]
    )
    assert (box(model, "28").amount_cents, box(model, "29").amount_cents) == (10_000, 2_100)
    assert [i.id for i in box(model, "29").items] == ["ok"]


def test_an_expense_with_two_lines_is_one_item_with_both_lines_added() -> None:  # AC-06
    model = build(expenses=[expense("a", [(21, 200_000, 42_000), (10, 50_000, 5_000)], label="Papelería S.L.")])
    (item,) = box(model, "28").items
    assert (item.kind, item.id, item.label) == ("expense", "a", "Papelería S.L.")
    assert (item.base_cents, item.vat_cents) == (250_000, 47_000)
    assert (box(model, "28").amount_cents, box(model, "29").amount_cents) == (250_000, 47_000)


def test_a_zero_rate_line_does_not_enter_and_an_expense_with_only_that_line_is_not_listed() -> None:  # AC-06, P-02
    model = build(
        expenses=[
            expense("mixed", [(0, 8_000, 0), (21, 1_000, 210)]),
            expense("zero", [(0, 5_000, 0)]),
            expense("manual", []),
        ]
    )
    assert (box(model, "28").amount_cents, box(model, "29").amount_cents) == (1_000, 210)
    assert [i.id for i in box(model, "28").items] == ["mixed"]
    assert model.result_kind == "a_compensar"


def test_the_rule_is_by_rate_so_a_zero_rate_line_adds_nothing_even_if_it_carried_an_amount() -> None:  # D-04
    model = build(expenses=[expense("a", [(0, 8_000, 77), (21, 1_000, 210)])])
    assert (box(model, "28").amount_cents, box(model, "29").amount_cents) == (1_000, 210)
    (item,) = box(model, "29").items
    assert (item.base_cents, item.vat_cents) == (1_000, 210)


def test_any_rate_above_zero_counts_in_28_and_29_not_only_4_10_and_21() -> None:
    model = build(expenses=[expense("a", [(5, 10_000, 500), ("7.5", 2_000, 150)])])
    assert (box(model, "28").amount_cents, box(model, "29").amount_cents) == (12_000, 650)


# --- AC-07 · el resultado ----------------------------------------------------------------------------------------------------------


def test_the_result_is_27_minus_45_with_its_sign_and_its_four_kinds() -> None:  # AC-07
    owed = build([invoice("a", 100_000, 21)], [expense("e", [(21, 10_000, 2_100)])])
    assert (owed.result_cents, owed.result_kind) == (21_000 - 2_100, "a_ingresar")
    credit = build([invoice("a", 10_000, 21)], [expense("e", [(21, 100_000, 21_000)])])
    assert (credit.result_cents, credit.result_kind) == (2_100 - 21_000, "a_compensar")
    zero = build([invoice("a", 10_000, 21)], [expense("e", [(21, 10_000, 2_100)])])
    assert (zero.result_cents, zero.result_kind) == (0, "a_cero")
    assert box(zero, "46").amount_cents == 0
    empty = build()
    assert (empty.result_cents, empty.result_kind) == (0, "sin_actividad")


def test_only_documents_that_add_nothing_make_a_zero_result_not_an_empty_quarter() -> None:
    model = build(expenses=[expense("no", [(21, 20_000, 4_200)], deductible=False)])
    assert model.result_kind == "a_cero"
    assert build(expenses=[expense("void", [(21, 20_000, 4_200)], voided=True)]).result_kind == "sin_actividad"


def test_the_derived_boxes_list_their_components_and_have_no_items() -> None:  # NFR-08
    model = build([invoice("a", 100_000, 21)], [expense("e", [(21, 10_000, 2_100)])])
    assert box(model, "27").components == ("03", "06", "09")
    assert box(model, "45").components == ("29",)
    assert box(model, "46").components == ("27", "45")
    for code in ("27", "45", "46"):
        assert box(model, code).items == () and box(model, code).measure is None
    got = amounts(model)
    assert (
        got["27"] == got["03"] + got["06"] + got["09"] and got["45"] == got["29"] and got["46"] == got["27"] - got["45"]
    )


def test_each_box_says_which_amount_of_its_items_it_adds() -> None:
    model = build()
    measures = {b.code: b.measure for b in model.boxes}
    assert measures == {
        "01": "base", "03": "vat", "04": "base", "06": "vat", "07": "base", "09": "vat", "27": None, "28": "base",
        "29": "vat", "45": None, "46": None, "59": "base", "120": "base",
    }  # fmt: skip
    groups = {b.code: b.group for b in model.boxes}
    assert (
        groups["27"] == "devengado"
        and groups["28"] == "deducible"
        and groups["46"] == "resultado"
        and groups["59"] == "adicional"
    )


# --- Fronteras del trimestre y documentos de otros trimestres -----------------------------------------------------------------------


def test_only_the_documents_of_the_quarter_count_and_the_borders_are_inclusive_then_exclusive() -> None:  # AC-09
    docs = [
        invoice("before", 1_000, 21, day=date(2025, 3, 31)),
        invoice("first", 2_000, 21, day=date(2025, 4, 1)),
        invoice("last", 4_000, 21, day=date(2025, 6, 30)),
        invoice("after", 8_000, 21, day=date(2025, 7, 1)),
    ]
    model = build(docs)
    assert [i.id for i in box(model, "07").items] == ["first", "last"]
    assert box(model, "07").amount_cents == 6_000
    spent = [
        expense("e1", [(21, 100, 21)], day=date(2025, 3, 31)),
        expense("e2", [(21, 200, 42)], day=date(2025, 4, 1)),
    ]
    assert [i.id for i in box(build(expenses=spent), "28").items] == ["e2"]


def test_a_document_of_another_quarter_changes_nothing() -> None:
    base = build([invoice("a", 10_000, 21)], [expense("e", [(21, 1_000, 210)])])
    noisy = build(
        [
            invoice("a", 10_000, 21),
            invoice("far", 999_999, 21, day=date(2024, 5, 10)),
            invoice("next", 5, 21, day=date(2025, 7, 1)),
        ],
        [expense("e", [(21, 1_000, 210)]), expense("far", [(21, 7, 1)], day=date(2026, 1, 1))],
    )
    assert noisy == base


def test_the_items_are_in_date_label_order_whatever_the_input_order() -> None:
    docs = [
        invoice("c", 100, 21, day=date(2025, 5, 3), label="B"),
        invoice("a", 100, 21, day=date(2025, 4, 3), label="Z"),
        invoice("b", 100, 21, day=date(2025, 5, 3), label="A"),
    ]
    assert [i.id for i in box(build(docs), "07").items] == ["a", "b", "c"]
    assert [i.id for i in box(build(list(reversed(docs))), "07").items] == ["a", "b", "c"]


def test_two_documents_with_the_same_date_and_label_are_ordered_by_id_so_the_output_is_deterministic() -> None:
    twins = [invoice(name, 100, 21, day=date(2025, 5, 3), label="Same") for name in ("z", "a", "m")]
    for order in (twins, list(reversed(twins)), [twins[1], twins[2], twins[0]]):
        assert [i.id for i in box(build(order), "07").items] == ["a", "m", "z"]


def test_the_same_documents_in_any_order_give_the_same_model() -> None:
    docs = [invoice(str(n), 1_000 + 37 * n, (4, 10, 21)[n % 3], day=date(2025, 4 + n % 3, 1 + n)) for n in range(12)]
    spent = [expense(f"e{n}", [(21, 500 + n, 105 + n)], day=date(2025, 4 + n % 3, 2 + n)) for n in range(6)]
    assert build(docs, spent) == build(list(reversed(docs)), list(reversed(spent)))


def test_building_the_model_does_not_change_the_input() -> None:
    docs = [invoice("a", 10_000, 21), invoice("b", 5_000, 10)]
    spent = [expense("e", [(21, 1_000, 210)])]
    before = (list(docs), list(spent))
    build(docs, spent)
    assert (docs, spent) == before


# --- AC-11 · el periodo ------------------------------------------------------------------------------------------------------------


def test_an_invalid_or_future_period_is_refused_before_looking_at_any_document() -> None:  # AC-11
    with pytest.raises(InvalidPeriod):
        build(quarter=5)
    with pytest.raises(PeriodInFuture):
        build(year=2026, quarter=4, today=date(2026, 9, 30))


# --- AC-12 · tipos que no existen ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("rate", [0, 5, "7.5", 20, "21.5", 22, 1])
def test_an_invoice_with_vat_and_a_rate_that_is_not_4_10_or_21_is_an_error_not_a_hidden_amount(
    rate: int | str,
) -> None:  # AC-12
    with pytest.raises(UnsupportedVatRate) as error:
        build([invoice("a", 10_000, rate, vat=100)])
    assert error.value.code == "unsupported_vat_rate"
    assert "10000" not in str(error.value) and "10.000" not in str(error.value)


@pytest.mark.parametrize("treatment", ["eu_reverse_charge", "non_eu_not_subject"])
@pytest.mark.parametrize(("rate", "vat"), [(21, 0), (0, 5), (21, 2_100)])
def test_an_operation_without_vat_that_carries_a_rate_or_a_vat_amount_is_inconsistent(
    treatment: str, rate: int, vat: int
) -> None:
    with pytest.raises(UnsupportedVatRate):
        build([invoice("a", 10_000, rate, vat=vat, treatment=treatment)])


def test_a_treatment_that_does_not_exist_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="desconocido"):
        build([invoice("a", 10_000, 21, treatment="something_else")])


def test_the_inconsistent_document_only_fails_when_it_is_in_the_quarter() -> None:
    other_quarter = invoice("bad", 10_000, 5, vat=500, day=date(2025, 8, 1))
    assert amounts(build([other_quarter, invoice("ok", 10_000, 21)]))["07"] == 10_000


# --- AC-16 · el límite de documentos ------------------------------------------------------------------------------------------------


def test_the_limit_of_documents_is_the_quarter_not_the_year() -> None:  # AC-16
    assert QUARTER_MAX_DOCUMENTS == 5_000
    docs = [invoice(str(n), 100, 21) for n in range(QUARTER_MAX_DOCUMENTS)]
    assert len(build(docs).boxes[4].items) == QUARTER_MAX_DOCUMENTS  # justo en el límite pasa
    with pytest.raises(QuarterTooLarge) as error:
        build([*docs, invoice("extra", 100, 21)])
    assert error.value.code == "quarter_too_large"


def test_invoices_and_expenses_count_together_towards_the_limit_but_voided_and_other_quarters_do_not() -> None:
    docs = [invoice(str(n), 100, 21) for n in range(3_000)]
    spent = [expense(str(n), [(21, 100, 21)]) for n in range(2_000)]
    build(docs, spent)  # 5.000 exactos
    with pytest.raises(QuarterTooLarge):
        build(docs, [*spent, expense("x", [(21, 100, 21)])])
    voided = [expense(f"v{n}", [(21, 100, 21)], voided=True) for n in range(100)]
    elsewhere = [invoice(f"o{n}", 100, 21, day=date(2025, 8, 1)) for n in range(100)]
    build([*docs, *elsewhere], [*spent, *voided])


# --- AC-21 · avisos fijos ------------------------------------------------------------------------------------------------------------


def test_the_fixed_notes_are_always_there_even_in_an_empty_quarter() -> None:  # AC-21
    for model in (build(), build([invoice("a", 10_000, 21)])):
        assert model.notes[:3] == (NOTE_303_DRAFT, NOTE_303_EXCLUSIONS, NOTE_303_CANARIAS)
        assert NOTE_303_349 not in model.notes
    assert "orientativo" in NOTE_303_DRAFT.lower()
    assert "Canarias, Ceuta y Melilla" in NOTE_303_CANARIAS and "IGIC" in NOTE_303_CANARIAS
    assert "inhábil" in NOTE_303_EXCLUSIONS


def test_the_349_note_appears_only_when_box_59_is_not_zero() -> None:  # AC-02, AC-21
    with_eu = build([invoice("a", 150_000, 0, vat=0, treatment="eu_reverse_charge")])
    assert with_eu.notes[-1] == NOTE_303_349 and len(with_eu.notes) == 4
    only_non_eu = build([invoice("a", 150_000, 0, vat=0, treatment="non_eu_not_subject")])
    assert NOTE_303_349 not in only_non_eu.notes
