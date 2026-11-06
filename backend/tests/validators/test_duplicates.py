"""AC-08 · Duplicados, duro y blando (SPEC-W-003 §5.1, D-04). La paridad con la columna generada de SQL llega con el hito 2."""

from datetime import date

import pytest

from cuadre.validators import ExistingExpense, normalize_invoice_number
from cuadre.validators.duplicates import is_hard_duplicate, is_possible_duplicate

DAY = date(2026, 11, 1)
OTHER_DAY = date(2026, 11, 2)


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("A-311", "A311"),
        ("a 311", "A311"),
        ("A311", "A311"),
        ("  A/311 ", "A311"),
        ("A.3-1 1", "A311"),
        ("001", "001"),  # los ceros no se quitan
        ("NS-2026-9921", "NS20269921"),
        ("Nº 5", "N5"),  # lo que no es ASCII alfanumérico se quita antes de pasar a mayúsculas
        ("ß12", "12"),
        ("١٢٣", None),  # cifras arábigas
        ("１２３", None),  # cifras de ancho completo
        ("---", None),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_the_invoice_number_key(raw: str | None, key: str | None) -> None:
    assert normalize_invoice_number(raw) == key


def test_variants_of_the_same_number_have_the_same_key() -> None:
    assert len({normalize_invoice_number(v) for v in ("A-311", "a 311", "A311", "a.311", "A_311")}) == 1


def existing(
    tax: str | None = "B00000042", number: str | None = "A311", day: date = DAY, total: int = 3000
) -> ExistingExpense:
    return ExistingExpense(supplier_tax_id=tax, invoice_number_key=number, expense_date=day, total_cents=total)


def test_a_hard_duplicate_needs_the_same_tax_id_and_the_same_number() -> None:
    assert is_hard_duplicate("B00000042", "A311", (existing(),))
    assert not is_hard_duplicate("B00000075", "A311", (existing(),))
    assert not is_hard_duplicate("B00000042", "A312", (existing(),))
    assert not is_hard_duplicate("B00000042", "A311", ())


def test_a_hard_duplicate_is_found_among_several_expenses() -> None:
    others = (existing(tax="B00000075"), existing(number="A999"), existing())
    assert is_hard_duplicate("B00000042", "A311", others)


@pytest.mark.parametrize(("tax", "number"), [(None, "A311"), ("B00000042", None), (None, None)])
def test_without_tax_id_or_number_there_is_no_hard_duplicate(tax: str | None, number: str | None) -> None:
    assert not is_hard_duplicate(tax, number, (existing(tax=tax, number=number),))


def test_a_possible_duplicate_is_the_same_day_total_and_tax_id_with_another_number_or_none() -> None:
    assert is_possible_duplicate("B00000042", "A312", DAY, 3000, (existing(),))
    assert is_possible_duplicate("B00000042", None, DAY, 3000, (existing(),))
    assert is_possible_duplicate("B00000042", None, DAY, 3000, (existing(number=None),))


def test_the_same_number_is_a_hard_duplicate_not_a_possible_one() -> None:
    assert not is_possible_duplicate("B00000042", "A311", DAY, 3000, (existing(),))


@pytest.mark.parametrize(
    ("tax", "day", "total"),
    [("B00000075", DAY, 3000), ("B00000042", OTHER_DAY, 3000), ("B00000042", DAY, 3001)],
)
def test_a_different_tax_id_day_or_total_is_not_a_possible_duplicate(tax: str, day: date, total: int) -> None:
    assert not is_possible_duplicate(tax, "A312", day, total, (existing(),))


@pytest.mark.parametrize(
    ("tax", "day", "total"), [(None, DAY, 3000), ("B00000042", None, 3000), ("B00000042", DAY, None)]
)
def test_a_possible_duplicate_needs_tax_id_day_and_total(tax: str | None, day: date | None, total: int | None) -> None:
    assert not is_possible_duplicate(tax, None, day, total, (existing(),))
