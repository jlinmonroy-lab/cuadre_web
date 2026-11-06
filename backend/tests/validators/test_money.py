"""Importes de los mensajes: céntimos enteros a «1.234,50 €» (es-ES), sin `float`."""

import pytest

from cuadre.validators.money import format_euros


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "0,00 €"),
        (5, "0,05 €"),
        (50, "0,50 €"),
        (14520, "145,20 €"),
        (99999, "999,99 €"),
        (100000, "1.000,00 €"),
        (123456, "1.234,56 €"),
        (100000000, "1.000.000,00 €"),
        (12345678901234, "123.456.789.012,34 €"),
        (-150, "-1,50 €"),
        (-123456, "-1.234,56 €"),
    ],
)
def test_format_euros(cents: int, text: str) -> None:
    assert format_euros(cents) == text
