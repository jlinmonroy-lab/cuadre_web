"""AC-16 · Guarda de dimensiones del logo y textos de la factura (SPEC-W-007 §5.1.6, B.1-A)."""

from datetime import date

import pytest

from cuadre.invoicing import logo_fits, long_date, numeric_date, rectification_reference
from cuadre.invoicing.limits import LOGO_MAX_PIXELS
from cuadre.invoicing.texts import MONTHS


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (300, 150, True),
        (1, 1, True),
        (2000, 2000, True),
        (4000, 1000, True),
        (1, 4_000_000, True),
        (2001, 2000, False),
        (2000, 2001, False),
        (4001, 1000, False),
        (4096, 4096, False),
        (9400, 9400, False),
        (0, 100, False),
        (100, 0, False),
        (-1, 100, False),
        (100, -5, False),
    ],
)
def test_a_logo_is_drawn_only_up_to_four_megapixels(width, height, expected) -> None:
    assert logo_fits(width, height) is expected


@pytest.mark.parametrize(
    "bad", [(None, 100), (100, None), (100.0, 100), (100, "100"), (True, 100), (100, False), ((100,), 100), ("a", "b")]
)
def test_dimensions_that_are_not_integers_do_not_fit(bad) -> None:
    assert logo_fits(*bad) is False


def test_the_limit_is_exactly_four_million_pixels() -> None:
    assert LOGO_MAX_PIXELS == 4_000_000
    assert logo_fits(LOGO_MAX_PIXELS, 1) and not logo_fits(LOGO_MAX_PIXELS + 1, 1)


def test_there_are_twelve_months_in_spanish_and_none_is_repeated() -> None:
    assert len(MONTHS) == len(set(MONTHS)) == 12
    assert MONTHS[0] == "enero" and MONTHS[8] == "septiembre" and MONTHS[11] == "diciembre"


@pytest.mark.parametrize(
    ("month", "name"),
    list(
        enumerate(
            [
                "enero",
                "febrero",
                "marzo",
                "abril",
                "mayo",
                "junio",
                "julio",
                "agosto",
                "septiembre",
                "octubre",
                "noviembre",
                "diciembre",
            ],
            start=1,
        )
    ),
)
def test_the_long_date_names_every_month(month, name) -> None:
    assert long_date(date(2026, month, 3)) == f"3 de {name} de 2026"


def test_the_long_date_does_not_pad_the_day() -> None:
    assert long_date(date(2026, 11, 3)) == "3 de noviembre de 2026"
    assert long_date(date(2026, 11, 10)) == "10 de noviembre de 2026"


def test_the_numeric_date_pads_day_and_month_for_the_messages() -> None:
    assert numeric_date(date(2026, 3, 9)) == "09/03/2026"
    assert numeric_date(date(2026, 12, 31)) == "31/12/2026"


def test_the_rectification_reference_names_the_original_and_its_date() -> None:
    assert (
        rectification_reference("2026-014", date(2026, 11, 3))
        == "Factura rectificativa de la 2026-014 de 3 de noviembre de 2026"
    )
