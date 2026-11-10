"""T7-01, AC-24 · Las constantes de SPEC-W-007 son las de la spec (la base de datos las repite; el hito 2 las compara con sus CHECK)."""

from cuadre.invoicing import limits as L
from cuadre.tax import limits as T


def test_the_text_and_amount_limits_are_the_ones_of_the_spec() -> None:
    assert (L.CONCEPT_MIN, L.CONCEPT_MAX) == (2, 300)
    assert (L.REASON_MIN, L.REASON_MAX) == (2, 300)
    assert (L.BASE_MIN, L.BASE_MAX) == (1, 9_999_999_999)
    assert (L.NUMBER_MIN, L.NUMBER_MAX, L.NUMBER_MIN_DIGITS) == (1, 999_999, 3)


def test_the_series_kinds_and_the_reserved_rectifying_code() -> None:
    assert L.SERIES_KINDS == ("standard", "rectifying")
    assert L.RECTIFYING_CODE.fullmatch("R-2026") and not L.RECTIFYING_CODE.fullmatch("R-26")


def test_the_pdf_and_logo_limits() -> None:
    assert L.LOGO_MAX_PIXELS == 4_000_000
    assert L.PDF_HASH_PREFIX == 16


def test_the_forbidden_text_categories_are_the_same_as_the_profile_and_the_clients() -> None:
    from cuadre.clients.limits import FORBIDDEN_CATEGORIES as clients
    from cuadre.profile.limits import FORBIDDEN_CATEGORIES as profile

    assert L.FORBIDDEN_CATEGORIES == clients == profile


def test_the_maximum_base_with_vat_and_no_withholding_fits_a_bigint() -> None:
    base = L.BASE_MAX
    assert base + (base * 21 + 99) // 100 < 2**63


def test_the_tax_limits() -> None:
    from decimal import Decimal

    assert (Decimal(21), Decimal(10), Decimal(4)) == T.VAT_RATES and Decimal(21) == T.DEFAULT_VAT_RATE
    assert T.TREATMENTS == (
        "national_vat",
        "eu_reverse_charge",
        "eu_consumer_vat",
        "non_eu_consumer_vat",
        "non_eu_not_subject",
    )
    assert len(set(T.TREATMENTS)) == 5
