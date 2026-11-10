"""Los textos puros del PDF (SPEC-W-007 §5.1.6): importes en es-ES, porcentajes, IBAN y el texto que Helvetica sí sabe dibujar."""

from decimal import Decimal

import pytest

from cuadre.invoicing.texts import format_euros, format_iban, format_percent, pdf_text


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "0,00 €"),
        (5, "0,05 €"),
        (99, "0,99 €"),
        (100, "1,00 €"),
        (120_000, "1.200,00 €"),
        (127_200, "1.272,00 €"),
        (100_000_000, "1.000.000,00 €"),
        (9_999_999_999, "99.999.999,99 €"),
        (-5, "-0,05 €"),
        (-21_200, "-212,00 €"),
        (-9_999_999_999, "-99.999.999,99 €"),
        (123_456_789, "1.234.567,89 €"),
    ],
)
def test_format_euros(cents: int, text: str) -> None:
    assert format_euros(cents) == text


@pytest.mark.parametrize("bad", [True, False, 1.5, "100", None, Decimal(100)])
def test_format_euros_only_takes_whole_cents(bad: object) -> None:
    with pytest.raises(ValueError):
        format_euros(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("rate", "text"),
    [
        (Decimal("21.00"), "21 %"),
        (Decimal("21"), "21 %"),
        (Decimal("10.00"), "10 %"),
        (Decimal("4.00"), "4 %"),
        (Decimal("15.00"), "15 %"),
        (Decimal("7.00"), "7 %"),
        (Decimal("0.00"), "0 %"),
        (Decimal("7.50"), "7,5 %"),
    ],
)
def test_format_percent(rate: Decimal, text: str) -> None:
    assert format_percent(rate) == text


def test_format_iban_in_groups_of_four() -> None:
    assert format_iban("ES3600000000050000000001") == "ES36 0000 0000 0500 0000 0001"
    assert format_iban("DE89370400440532013000") == "DE89 3704 0044 0532 0130 00"
    assert format_iban("ES") == "ES"


@pytest.mark.parametrize(
    "text",
    [
        "Muñoz Pérez, S.L.",
        "Diseño — 1.200,00 € ½ ¿Qué?",
        "Ünal Şahin".replace("Ş", "S"),
        "Straße 5",
        "ÀÉÎÕÜ àéîõü",
        "“comillas” ‘simples’ – raya",
    ],
)
def test_what_winansi_can_draw_passes_untouched(text: str) -> None:
    assert pdf_text(text) == text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Łukasz", "Lukasz"),
        ("łódź", "lódz"),  # ó cabe en WinAnsi; ł y ź no
        ("Şahin Ğ", "Sahin G"),
        ("İstanbul ı", "Istanbul i"),
        ("Đorđe", "Dorde"),
        ("Šimůnek Čech", "Šimunek Cech"),  # Š y Ž sí están en WinAnsi; ů y Č no
        ("Привет", "??????"),
        ("日本語", "???"),
        ("😀", "?"),
        ("ǆ", "d"),
        ("ǆ ß", "d ß"),
    ],
)
def test_what_helvetica_cannot_draw_is_lowered_or_marked(raw: str, expected: str) -> None:
    assert pdf_text(raw) == expected


def test_controls_and_line_breaks_never_reach_the_drawing() -> None:
    assert pdf_text("a\nb\r\nc\td") == "a b  c d"
    assert pdf_text("a​b‮c d") == "abcd"
    assert pdf_text("") == ""


def test_the_result_always_fits_winansi() -> None:
    for raw in ("Łukasz Şahin Привет 日本語 😀 Muñoz € ½ ǆ ŉ ẞ", "ﬁ ﬂ ﬃ ① ㎏ ℃"):
        pdf_text(raw).encode("cp1252")
