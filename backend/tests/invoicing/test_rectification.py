"""AC-14, AC-15 · Rectificativas por diferencia de valores (SPEC-W-007 §5.1.5, D-12; art. 15.4 y 15.5 del Reglamento de facturación)."""

import random
from datetime import date
from decimal import Decimal

import pytest

from cuadre.invoicing import RawRectification, standing_of, validate_invoice, validate_rectification
from cuadre.tax import Amounts
from cuadre.validators.vat import percentage_of
from tests.invoicing.support import (
    IRPF,
    LF,
    ORIGINAL_ID,
    RECT_SERIES_ID,
    TODAY,
    ZERO_WIDTH,
    client,
    original,
    raw,
    raw_rectification,
    rect_series,
    series,
)

TEXT = {
    "reason": "Escribe el motivo de la rectificación.",
    "reason_length": "El motivo admite entre 2 y 300 caracteres, sin saltos de línea.",
    "corrected_base": "Escribe la base corregida (0 si se anula la factura).",
    "corrected_nothing": "La base corregida es igual a la actual: no hay nada que rectificar.",
    "exceeds": "Una rectificativa no puede subir el importe: emite una factura nueva.",
    "not_rectifiable": "Una factura rectificativa no se puede rectificar: rectifica la original.",
    "date": "Elige la fecha de expedición.",
    "date_future": "La fecha no puede ser futura.",
}


def rectify(orig=None, previous=(), se=None, **fields):
    return validate_rectification(
        raw_rectification(**fields),
        original=orig if orig is not None else original(),
        rectifications=previous,
        series=se if se is not None else rect_series(),
        today=TODAY,
    )


def errors(result) -> dict[str, str]:
    return {e.field: e.message for e in result.errors}


# --- AC-14 ---------------------------------------------------------------------------------------------------------------------


def test_ac_14_a_rectification_that_lowers_the_base() -> None:
    result = rectify(corrected_base_cents=100_000)
    v = result.values
    assert v is not None and result.errors == () and result.problem is None
    a = v.amounts
    assert (a.base_cents, a.vat_cents, a.irpf_cents, a.total_cents) == (-20_000, -4_200, -3_000, -21_200)
    assert (str(a.vat_rate), str(a.irpf_rate)) == ("21.00", "15.00")
    assert (v.original_id, v.series_id, v.corrected_base_cents, v.reason, v.issue_date) == (
        ORIGINAL_ID,
        RECT_SERIES_ID,
        100_000,
        "Importe corregido",
        TODAY,
    )


def test_ac_14_the_second_rectification_cancels_the_rest() -> None:
    orig = original()
    first = rectify(orig, corrected_base_cents=100_000).values
    assert first is not None
    second = rectify(orig, previous=[first.amounts], corrected_base_cents=0, reason="Anulación").values
    assert second is not None
    assert (
        second.amounts.base_cents,
        second.amounts.vat_cents,
        second.amounts.irpf_cents,
        second.amounts.total_cents,
    ) == (-100_000, -21_000, -15_000, -106_000 + 0)
    standing = standing_of(orig.amounts, [first.amounts, second.amounts])
    assert (standing.base_cents, standing.vat_cents, standing.irpf_cents) == (0, 0, 0)
    assert orig.amounts.total_cents + first.amounts.total_cents + second.amounts.total_cents == 0


def test_the_rectification_inherits_the_treatment_the_note_and_the_rates_of_the_original() -> None:
    eu = original("eu", "business", base=150_000, irpf=None)
    v = rectify(eu, corrected_base_cents=100_000).values
    assert v is not None
    assert (v.tax_treatment, v.legal_note) == ("eu_reverse_charge", "Inversión del sujeto pasivo.")
    assert (v.amounts.vat_cents, v.amounts.irpf_cents, v.amounts.total_cents) == (0, 0, -50_000)
    ten = original("national", "individual", base=100_000, vat=Decimal(10), irpf=None)
    w = rectify(ten, corrected_base_cents=50_000).values
    assert w is not None and (str(w.amounts.vat_rate), w.amounts.vat_cents) == ("10.00", -5_000)


def test_the_chain_of_105_at_10_percent_in_two_steps_ends_at_zero_to_the_cent() -> None:
    orig = original("national", "individual", base=105, vat=Decimal(10), irpf=None)
    first = rectify(orig, corrected_base_cents=53).values
    assert first is not None and first.amounts.base_cents == -52
    second = rectify(orig, previous=[first.amounts], corrected_base_cents=0).values
    assert second is not None and second.amounts.base_cents == -53
    s = standing_of(orig.amounts, [first.amounts, second.amounts])
    assert (s.base_cents, s.vat_cents, s.irpf_cents) == (0, 0, 0)


def test_a_chain_of_validated_rectifications_equals_the_direct_computation_with_random_data() -> None:
    rng = random.Random(20261110)
    for _ in range(1_500):
        base = rng.randint(1, 50_000) if rng.random() < 0.7 else rng.randint(1, 9_999_999_999)
        vat, irpf = Decimal(rng.choice((21, 10, 4))), Decimal(rng.choice((7, 15)))
        orig = original(base=base, vat=vat, irpf=irpf)
        previous: list[Amounts] = []
        current = base
        for _step in range(rng.randint(1, 5)):
            if current == 0:
                break
            target = rng.randint(0, current - 1)
            v = rectify(orig, previous=previous, corrected_base_cents=target).values
            assert v is not None
            previous.append(v.amounts)
            current = target
            s = standing_of(orig.amounts, previous)
            assert (s.base_cents, s.vat_cents, s.irpf_cents) == (
                target,
                percentage_of(target, vat),
                percentage_of(target, irpf),
            )


def test_standing_adds_the_original_and_every_difference() -> None:
    orig = original()
    s = standing_of(orig.amounts, [])
    assert (s.base_cents, s.vat_cents, s.irpf_cents) == (120_000, 25_200, 18_000)
    parts = [Amounts(-10, Decimal(21), -2, Decimal(15), -1, -11), Amounts(-5, Decimal(21), -1, Decimal(15), -1, -5)]
    s2 = standing_of(orig.amounts, parts)
    assert (s2.base_cents, s2.vat_cents, s2.irpf_cents) == (119_985, 25_197, 17_998)


# --- AC-15: límites -------------------------------------------------------------------------------------------------------------


def test_ac_15_a_rectification_cannot_be_rectified() -> None:
    rectifying = original(kind="rectifying")
    p = rectify(rectifying).problem
    assert p is not None and (p.code, p.status, p.field, p.message) == (
        "invoice_not_rectifiable",
        409,
        None,
        TEXT["not_rectifiable"],
    )


def test_ac_15_that_problem_comes_before_any_field_error() -> None:
    result = validate_rectification(
        RawRectification(), original=original(kind="rectifying"), rectifications=[], series=rect_series(), today=TODAY
    )
    assert result.errors == () and result.problem is not None and result.problem.code == "invoice_not_rectifiable"


def test_ac_15_a_rectification_cannot_raise_the_amount() -> None:
    p = rectify(corrected_base_cents=120_001).problem
    assert p is not None and (p.code, p.status, p.field, p.message) == (
        "rectification_exceeds",
        409,
        "corrected_base_cents",
        TEXT["exceeds"],
    )
    assert rectify(corrected_base_cents=119_999).values is not None


def test_ac_15_the_current_base_after_other_rectifications_is_the_ceiling() -> None:
    orig = original()
    first = rectify(orig, corrected_base_cents=100_000).values
    assert first is not None
    assert rectify(orig, previous=[first.amounts], corrected_base_cents=100_001).problem.code == "rectification_exceeds"  # type: ignore[union-attr]
    assert rectify(orig, previous=[first.amounts], corrected_base_cents=99_999).values is not None


def test_ac_15_the_same_base_is_a_field_error_and_also_when_it_is_already_zero() -> None:
    assert errors(rectify(corrected_base_cents=120_000)) == {"corrected_base_cents": TEXT["corrected_nothing"]}
    orig = original()
    cancel = rectify(orig, corrected_base_cents=0).values
    assert cancel is not None
    assert errors(rectify(orig, previous=[cancel.amounts], corrected_base_cents=0)) == {
        "corrected_base_cents": TEXT["corrected_nothing"]
    }


@pytest.mark.parametrize(
    "bad", [None, True, False, "100000", "0", 100_000.0, 0.0, -1, -100_000, 9_999_999_999 + 1, 10**30, [1], {}]
)
def test_ac_15_the_corrected_base_is_an_integer_from_zero_up(bad) -> None:
    assert errors(rectify(corrected_base_cents=bad)) == {"corrected_base_cents": TEXT["corrected_base"]}


def test_ac_15_zero_is_a_valid_corrected_base_and_false_is_not() -> None:
    assert rectify(corrected_base_cents=0).values is not None
    assert errors(rectify(corrected_base_cents=False)) == {"corrected_base_cents": TEXT["corrected_base"]}


@pytest.mark.parametrize("bad", [None, "", "   ", 5, True])
def test_ac_15_the_reason_is_required(bad) -> None:
    assert errors(rectify(reason=bad)) == {"reason": TEXT["reason"]}


@pytest.mark.parametrize("bad", ["a", " a ", "x" * 301, "motivo" + LF + "otro", "motivo" + ZERO_WIDTH])
def test_the_reason_is_two_to_300_characters_on_one_line(bad) -> None:
    assert errors(rectify(reason=bad)) == {"reason": TEXT["reason_length"]}


def test_the_reason_bounds_are_inclusive_and_it_is_trimmed() -> None:
    assert rectify(reason="ab").values is not None
    assert rectify(reason="x" * 300).values is not None
    v = rectify(reason="  Importe corregido  ").values
    assert v is not None and v.reason == "Importe corregido"


def test_all_the_field_errors_come_at_once_in_the_order_of_the_screen() -> None:
    result = validate_rectification(
        RawRectification(), original=original(), rectifications=[], series=rect_series(), today=TODAY
    )
    assert [(e.field, e.message) for e in result.errors] == [
        ("reason", TEXT["reason"]),
        ("corrected_base_cents", TEXT["corrected_base"]),
        ("issue_date", TEXT["date"]),
    ]


def test_field_errors_hide_the_problems_that_would_come_after() -> None:
    result = rectify(reason="", corrected_base_cents=999_999)  # además sube el importe
    assert [e.field for e in result.errors] == ["reason"] and result.problem is None


def test_a_future_or_missing_date_is_a_field_error() -> None:
    assert errors(rectify(issue_date="2026-11-11")) == {"issue_date": TEXT["date_future"]}
    assert errors(rectify(issue_date="2026-02-30")) == {"issue_date": TEXT["date"]}
    assert errors(rectify(issue_date=None)) == {"issue_date": TEXT["date"]}


def test_a_date_before_the_original_is_a_problem_and_the_same_day_is_fine() -> None:
    orig = original()  # expedida el 3 de noviembre
    p = rectify(orig, issue_date="2026-11-02").problem
    assert p is not None and (p.code, p.status, p.field) == ("invoice_date_out_of_order", 409, "issue_date")
    assert p.message == "La fecha no puede ser anterior a la de la factura que se rectifica (03/11/2026)."
    assert rectify(orig, issue_date="2026-11-03").values is not None


def test_a_date_before_the_last_of_the_rectifying_series_is_a_problem_and_the_same_day_is_fine() -> None:
    last = rect_series(last_issue_date=date(2026, 11, 8))
    p = rectify(se=last, issue_date="2026-11-07").problem
    assert p is not None and (p.code, p.field) == ("invoice_date_out_of_order", "issue_date")
    assert p.message == "La fecha no puede ser anterior a la de la última factura de la serie (08/11/2026)."
    assert rectify(se=last, issue_date="2026-11-08").values is not None


def test_the_exceeding_problem_comes_before_the_date_problems() -> None:
    p = rectify(corrected_base_cents=999_999, issue_date="2026-11-02").problem
    assert p is not None and p.code == "rectification_exceeds"


def test_the_date_against_the_original_comes_before_the_one_against_the_series() -> None:
    p = rectify(se=rect_series(last_issue_date=date(2026, 11, 9)), issue_date="2026-11-02").problem
    assert p is not None and "rectifica" in p.message


@pytest.mark.parametrize("wrong", [series(), rect_series(archived=True)])
def test_the_series_of_a_rectification_is_the_active_rectifying_one(wrong) -> None:
    with pytest.raises(ValueError):
        rectify(se=wrong)


def test_a_rectification_of_a_full_invoice_issued_through_the_validator_end_to_end() -> None:
    result = validate_invoice(raw(), client=client(), series=series(), irpf_rate=IRPF, today=TODAY)
    assert result.values is not None
    assert rectify(corrected_base_cents=1).values is not None
