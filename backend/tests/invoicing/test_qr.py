"""AC-17 · Contenido del QR de VeriFactu simulado (SPEC-W-007 D-11, §5.1.6, RES-04, B.1-B)."""

from datetime import date

import pytest

from cuadre.invoicing import display_number, format_qr_amount, format_qr_date, qr_payload
from cuadre.invoicing.limits import QR_CAPTION, QR_LEVEL, QR_PREFIX, QR_SIZE_MM


def test_the_payload_of_an_ordinary_invoice_is_the_exact_text() -> None:
    assert (
        qr_payload("12345678Z", "2026-014", date(2026, 11, 10), 127_200)
        == "CUADRE-VERIFACTU-SIMULADO|12345678Z|2026-014|10-11-2026|1272.00"
    )


def test_the_payload_of_a_rectification_carries_the_negative_amount() -> None:
    assert (
        qr_payload("12345678Z", "R-2026-001", date(2026, 11, 10), -21_200)
        == "CUADRE-VERIFACTU-SIMULADO|12345678Z|R-2026-001|10-11-2026|-212.00"
    )


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "0.00"),
        (1, "0.01"),
        (9, "0.09"),
        (10, "0.10"),
        (99, "0.99"),
        (100, "1.00"),
        (127_200, "1272.00"),
        (-1, "-0.01"),
        (-21_200, "-212.00"),
        (-127_200, "-1272.00"),
        (9_999_999_999, "99999999.99"),
        (10**15, "10000000000000.00"),
    ],
)
def test_the_amount_uses_a_dot_and_two_decimals_with_no_thousands_separator(cents, expected) -> None:
    assert format_qr_amount(cents) == expected


@pytest.mark.parametrize("bad", [1.5, 12.0, "100", None, True, False])
def test_the_amount_is_an_integer_number_of_cents(bad) -> None:
    with pytest.raises(ValueError):
        format_qr_amount(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 11, 10), "10-11-2026"),
        (date(2026, 1, 5), "05-01-2026"),
        (date(2000, 1, 1), "01-01-2000"),
        (date(2026, 12, 31), "31-12-2026"),
        (date(999, 2, 3), "03-02-0999"),
    ],
)
def test_the_date_is_dd_mm_aaaa_with_hyphens_as_the_real_qr_asks(value, expected) -> None:
    assert format_qr_date(value) == expected


@pytest.mark.parametrize(
    ("nif", "number"),
    [("", "2026-001"), ("12345678Z", ""), ("123|45678Z", "2026-001"), ("12345678Z", "2026|001"), ("|", "x")],
)
def test_an_empty_field_or_one_with_the_separator_is_a_programming_error(nif, number) -> None:
    with pytest.raises(ValueError):
        qr_payload(nif, number, date(2026, 11, 10), 100)


def test_the_payload_has_five_fields_whatever_the_data_are() -> None:
    for nif in ("12345678Z", "B00000018", "X1234567L"):
        for code, n in (("2026", 1), ("R-2026", 999_999), ("A-B", 1000)):
            text = qr_payload(nif, display_number(code, n), date(2026, 11, 10), -1)
            assert text.count("|") == 4 and text.split("|")[0] == QR_PREFIX


def test_the_worst_real_case_fits_the_version_5_in_byte_mode() -> None:
    """El emisor tiene NIF español (9 caracteres), la serie 8 y el número 6 dígitos, y el total no pasa de ±105.999.999,99 €. Como el texto lleva
    `|` (fuera del alfabeto del QR), va en modo de bytes: la versión 5 de nivel M admite 84 (B.1-A midió 63 y 71 caracteres, no 120 de bytes)."""
    nif = "B" + "0" * 7 + "8"
    number = display_number("ABCDEFGH", 999_999)
    for total in (10_599_999_999, -10_599_999_999, 0, -1):
        text = qr_payload(nif, number, date(2026, 11, 10), total)
        assert len(text) <= 84 and len(text.encode("utf-8")) == len(text)
    assert len(qr_payload(nif, number, date(2026, 11, 10), -10_599_999_999)) == 76


def test_the_payload_is_not_a_url_so_it_cannot_be_resolved() -> None:
    text = qr_payload("12345678Z", "2026-014", date(2026, 11, 10), 100)
    assert "://" not in text and "agenciatributaria" not in text.lower() and "ValidarQR" not in text


def test_the_caption_the_size_and_the_level() -> None:
    assert QR_CAPTION == "QR VeriFactu simulado, no remitido a la AEAT"
    assert "VERI*FACTU" not in QR_CAPTION and "simulado" in QR_CAPTION
    assert (QR_SIZE_MM, QR_LEVEL) == (35, "M")
    assert 30 <= QR_SIZE_MM <= 40
    assert QR_PREFIX == "CUADRE-VERIFACTU-SIMULADO"
