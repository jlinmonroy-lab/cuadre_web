"""AC-01 a AC-04, AC-14 · Importes de una factura y de una rectificativa (SPEC-W-007 §5.1.3 y §5.1.5, RES-02)."""

import random
from decimal import Decimal

import pytest

from cuadre.tax import Amounts, Standing, compute_amounts, invoice_terms, rectification_amounts
from cuadre.validators.vat import percentage_of

NATIONAL_COMPANY = invoice_terms("national", "business")
NATIONAL_PERSON = invoice_terms("national", "individual")
EU_COMPANY = invoice_terms("eu", "business")
EU_PERSON = invoice_terms("eu", "individual")
NON_EU_COMPANY = invoice_terms("non_eu", "business")
NON_EU_PERSON = invoice_terms("non_eu", "individual")


def half_up(base: int, rate: int) -> int:
    """El oráculo: `base × tipo / 100` redondeado medio hacia arriba, con solo enteros (para base ≥ 0)."""
    return (base * rate * 2 + 100) // 200


# --- La tabla de §5.1.3 --------------------------------------------------------------------------------------------------------

# (condiciones, base, tipo elegido, retención del perfil, IVA, retención, total)
TABLE = [
    (NATIONAL_COMPANY, 120_000, None, Decimal(15), 25_200, 18_000, 127_200),  # AC-01
    (NATIONAL_COMPANY, 120_000, Decimal(21), Decimal(7), 25_200, 8_400, 136_800),
    (EU_COMPANY, 150_000, None, None, 0, 0, 150_000),  # US-006 / AC-02
    (EU_PERSON, 100_000, None, None, 21_000, 0, 121_000),
    (NON_EU_COMPANY, 50_000, None, None, 0, 0, 50_000),
    (NON_EU_PERSON, 100_000, None, None, 21_000, 0, 121_000),  # P-05
    (NATIONAL_PERSON, 100_000, None, None, 21_000, 0, 121_000),
    (NATIONAL_PERSON, 100_000, Decimal(10), None, 10_000, 0, 110_000),
    (NATIONAL_PERSON, 100_000, Decimal(4), None, 4_000, 0, 104_000),
    (NATIONAL_PERSON, 1_050, Decimal(10), None, 105, 0, 1_155),  # AC-04: 10,50 € al 10 %
]


@pytest.mark.parametrize(("terms", "base", "vat_rate", "irpf_rate", "vat", "irpf", "total"), TABLE)
def test_the_amounts_of_the_table(terms, base, vat_rate, irpf_rate, vat, irpf, total) -> None:
    amounts = compute_amounts(terms, base, vat_rate, irpf_rate)
    assert (amounts.base_cents, amounts.vat_cents, amounts.irpf_cents, amounts.total_cents) == (base, vat, irpf, total)


def test_the_rates_come_with_two_decimals() -> None:
    a = compute_amounts(NATIONAL_COMPANY, 120_000, None, Decimal(15))
    assert (str(a.vat_rate), str(a.irpf_rate)) == ("21.00", "15.00")
    b = compute_amounts(EU_COMPANY, 150_000, None, None)
    assert (str(b.vat_rate), str(b.irpf_rate)) == ("0.00", "0.00")


@pytest.mark.parametrize(
    ("base", "rate", "expected"),
    [
        (1_050, 10, 105),
        (1_055, 10, 106),
        (5, 10, 1),
        (4, 10, 0),
        (1, 21, 0),
        (3, 21, 1),
        (50, 21, 11),
        (49, 21, 10),
        (25, 4, 1),
        (12, 4, 0),
        (13, 4, 1),
    ],
)
def test_half_a_cent_rounds_up(base, rate, expected) -> None:
    assert compute_amounts(NATIONAL_PERSON, base, Decimal(rate), None).vat_cents == expected == half_up(base, rate)


def test_the_largest_invoice_fits_in_a_bigint_and_rounds_like_the_oracle() -> None:
    base = 9_999_999_999
    a = compute_amounts(NATIONAL_COMPANY, base, Decimal(21), Decimal(15))
    assert (a.vat_cents, a.irpf_cents) == (half_up(base, 21), half_up(base, 15)) == (2_100_000_000, 1_500_000_000)
    assert a.total_cents == base + 2_100_000_000 - 1_500_000_000 < 2**63


def test_a_rate_is_only_used_when_the_treatment_has_vat() -> None:
    assert compute_amounts(EU_COMPANY, 100_000, Decimal(21), None).vat_cents == 0
    assert compute_amounts(NON_EU_COMPANY, 100_000, Decimal(10), None).vat_cents == 0


def test_a_missing_vat_rate_uses_the_default_of_the_treatment() -> None:
    assert compute_amounts(NATIONAL_PERSON, 100_000, None, None).vat_rate == Decimal("21.00")


def test_a_retention_is_only_used_when_the_treatment_withholds() -> None:
    assert compute_amounts(NATIONAL_PERSON, 100_000, None, Decimal(15)).irpf_cents == 0
    assert compute_amounts(EU_PERSON, 100_000, None, Decimal(15)).irpf_cents == 0


def test_a_company_that_withholds_needs_the_retention_rate() -> None:
    with pytest.raises(ValueError):
        compute_amounts(NATIONAL_COMPANY, 100_000, None, None)


def test_an_ordinary_invoice_never_has_a_negative_base() -> None:
    with pytest.raises(ValueError):
        compute_amounts(NATIONAL_PERSON, -1, None, None)


def test_a_zero_base_gives_zero_everywhere() -> None:
    a = compute_amounts(NATIONAL_COMPANY, 0, None, Decimal(15))
    assert (a.vat_cents, a.irpf_cents, a.total_cents) == (0, 0, 0)


def test_the_identity_total_equals_base_plus_vat_minus_withholding_with_random_data() -> None:
    rng = random.Random(20261110)
    combos = [
        (NATIONAL_COMPANY, 15),
        (NATIONAL_COMPANY, 7),
        (NATIONAL_PERSON, 0),
        (EU_PERSON, 0),
        (EU_COMPANY, 0),
        (NON_EU_PERSON, 0),
        (NON_EU_COMPANY, 0),
    ]
    for _ in range(5_000):
        terms, irpf = rng.choice(combos)
        base = rng.choice((rng.randint(1, 1_000), rng.randint(1, 10_000_000), rng.randint(1, 9_999_999_999)))
        rate = rng.choice((10, 21, 4)) if terms.vat_editable else 0
        a = compute_amounts(
            terms, base, Decimal(rate) if terms.vat_editable else None, Decimal(irpf) if terms.withholds else None
        )
        assert a.vat_cents == half_up(base, rate)
        assert a.irpf_cents == (half_up(base, irpf) if terms.withholds else 0)
        assert a.total_cents == base + a.vat_cents - a.irpf_cents
        assert isinstance(a.total_cents, int)


# --- Rectificativas: la diferencia de valores ----------------------------------------------------------------------------------


def standing_of_invoice(a: Amounts) -> Standing:
    return Standing(a.base_cents, a.vat_cents, a.irpf_cents)


def test_ac_14_a_rectification_that_lowers_the_base() -> None:
    original = compute_amounts(NATIONAL_COMPANY, 120_000, None, Decimal(15))
    r = rectification_amounts(standing_of_invoice(original), Decimal(21), Decimal(15), 100_000)
    assert (r.base_cents, r.vat_cents, r.irpf_cents, r.total_cents) == (-20_000, -4_200, -3_000, -21_200)
    assert (str(r.vat_rate), str(r.irpf_rate)) == ("21.00", "15.00")


def test_ac_14_a_full_cancellation_returns_everything_including_the_withholding() -> None:
    original = compute_amounts(NATIONAL_COMPANY, 120_000, None, Decimal(15))
    r = rectification_amounts(standing_of_invoice(original), Decimal(21), Decimal(15), 0)
    assert (r.base_cents, r.vat_cents, r.irpf_cents, r.total_cents) == (-120_000, -25_200, -18_000, -127_200)


def test_two_steps_leave_the_invoice_at_zero() -> None:
    original = compute_amounts(NATIONAL_COMPANY, 120_000, None, Decimal(15))
    first = rectification_amounts(standing_of_invoice(original), Decimal(21), Decimal(15), 100_000)
    after_first = Standing(
        original.base_cents + first.base_cents,
        original.vat_cents + first.vat_cents,
        original.irpf_cents + first.irpf_cents,
    )
    second = rectification_amounts(after_first, Decimal(21), Decimal(15), 0)
    assert (second.base_cents, second.vat_cents, second.irpf_cents) == (-100_000, -21_000, -15_000)
    assert original.total_cents + first.total_cents + second.total_cents == 0


def test_the_percentage_of_a_negative_amount_would_drift_and_the_difference_of_values_does_not() -> None:
    """El hallazgo del hito 1: base 105 al 10 % lleva 11 de IVA; anulada en −52 y −53, el porcentaje del negativo da −5 y −5 y deja 1 vigente."""
    original = compute_amounts(NATIONAL_PERSON, 105, Decimal(10), None)
    assert original.vat_cents == 11
    naive_vat = original.vat_cents + percentage_of(-52, Decimal(10)) + percentage_of(-53, Decimal(10))
    assert naive_vat == 1  # con base 0 y una cuota vigente de 1 céntimo: lo que esta spec evita
    first = rectification_amounts(standing_of_invoice(original), Decimal(10), Decimal(0), 53)
    after_first = Standing(original.base_cents + first.base_cents, original.vat_cents + first.vat_cents, 0)
    second = rectification_amounts(after_first, Decimal(10), Decimal(0), 0)
    assert (first.base_cents, second.base_cents) == (-52, -53)
    assert original.vat_cents + first.vat_cents + second.vat_cents == 0
    assert original.total_cents + first.total_cents + second.total_cents == 0


def test_a_chain_of_rectifications_always_equals_the_direct_computation_with_random_data() -> None:
    rng = random.Random(20261110)
    for _ in range(3_000):
        base = rng.randint(1, 100_000) if rng.random() < 0.7 else rng.randint(1, 9_999_999_999)
        vat, irpf = Decimal(rng.choice((21, 10, 4))), Decimal(rng.choice((0, 7, 15)))
        original = compute_amounts(NATIONAL_COMPANY, base, vat, irpf)
        standing = standing_of_invoice(original)
        total = original.total_cents
        current = base
        for _step in range(rng.randint(1, 5)):
            target = rng.randint(0, current) if current > 0 else 0
            if target == current:
                continue
            r = rectification_amounts(standing, vat, irpf, target)
            standing = Standing(
                standing.base_cents + r.base_cents, standing.vat_cents + r.vat_cents, standing.irpf_cents + r.irpf_cents
            )
            total += r.total_cents
            current = target
            assert standing.base_cents == target
            assert standing.vat_cents == percentage_of(target, vat)
            assert standing.irpf_cents == percentage_of(target, irpf)
            assert total == target + standing.vat_cents - standing.irpf_cents
            assert r.total_cents == r.base_cents + r.vat_cents - r.irpf_cents


def test_a_rectification_may_also_go_up_in_the_function_and_the_rule_that_forbids_it_lives_in_validation() -> None:
    original = compute_amounts(NATIONAL_PERSON, 100_000, Decimal(21), None)
    r = rectification_amounts(standing_of_invoice(original), Decimal(21), Decimal(0), 110_000)
    assert (r.base_cents, r.vat_cents, r.total_cents) == (10_000, 2_100, 12_100)


def test_a_corrected_base_is_never_negative() -> None:
    with pytest.raises(ValueError):
        rectification_amounts(Standing(100, 21, 0), Decimal(21), Decimal(0), -1)
