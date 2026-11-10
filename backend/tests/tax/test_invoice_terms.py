"""AC-01 a AC-03 · Condiciones fiscales por ámbito y tipo del cliente (SPEC-W-007 §5.1.2, D-05)."""

from decimal import Decimal

import pytest

from cuadre.tax import DEFAULT_VAT_RATE, NOTE_NON_EU, NOTE_REVERSE_CHARGE, TREATMENTS, VAT_RATES, invoice_terms

# (ámbito, tipo, tratamiento, ¿IVA elegible?, tipo por defecto, ¿retención?, mención). Escrita a mano desde la tabla de §5.1.2, no desde el código.
TABLE = [
    ("national", "business", "national_vat", True, Decimal(21), True, None),
    ("national", "individual", "national_vat", True, Decimal(21), False, None),
    ("eu", "business", "eu_reverse_charge", False, Decimal(0), False, "Inversión del sujeto pasivo."),
    ("eu", "individual", "eu_consumer_vat", True, Decimal(21), False, None),
    (
        "non_eu",
        "business",
        "non_eu_not_subject",
        False,
        Decimal(0),
        False,
        "Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA).",
    ),
    ("non_eu", "individual", "non_eu_consumer_vat", True, Decimal(21), False, None),
]


@pytest.mark.parametrize(("scope", "kind", "treatment", "editable", "rate", "withholds", "note"), TABLE)
def test_each_client_gets_the_conditions_of_the_table(scope, kind, treatment, editable, rate, withholds, note) -> None:
    terms = invoice_terms(scope, kind)
    assert (terms.treatment, terms.vat_editable, terms.vat_rate, terms.withholds, terms.legal_note) == (
        treatment,
        editable,
        rate,
        withholds,
        note,
    )


def test_the_five_treatments_are_all_reachable_and_nothing_else() -> None:
    reached = {invoice_terms(scope, kind).treatment for scope, kind, *_ in TABLE}
    assert reached == set(TREATMENTS)
    assert len(TREATMENTS) == 5


def test_only_a_spanish_company_withholds() -> None:
    withholders = [(s, k) for s, k, *_ in TABLE if invoice_terms(s, k).withholds]
    assert withholders == [("national", "business")]


def test_a_client_without_vat_is_exactly_a_company_outside_spain() -> None:
    no_vat = {(s, k) for s, k, *_ in TABLE if not invoice_terms(s, k).vat_editable}
    assert no_vat == {("eu", "business"), ("non_eu", "business")}
    for scope, kind in no_vat:
        assert invoice_terms(scope, kind).vat_rate == 0


def test_a_consumer_outside_spain_pays_spanish_vat_whatever_the_country() -> None:
    """P-05 (decidida el 2026-11-10, B.1-B): a un particular de la UE o de fuera de la UE se le aplica IVA español."""
    for scope in ("eu", "non_eu"):
        terms = invoice_terms(scope, "individual")
        assert terms.vat_editable and terms.vat_rate == DEFAULT_VAT_RATE and terms.legal_note is None


def test_the_legal_notes_are_the_exact_texts() -> None:
    assert NOTE_REVERSE_CHARGE == "Inversión del sujeto pasivo."
    assert NOTE_NON_EU == "Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA)."
    # Solo las dos empresas sin IVA llevan mención; ningún otro tratamiento lleva una.
    assert [invoice_terms(s, k).legal_note is not None for s, k, *_ in TABLE] == [
        False,
        False,
        True,
        False,
        True,
        False,
    ]


def test_the_vat_rates_are_21_10_and_4() -> None:
    assert (Decimal(21), Decimal(10), Decimal(4)) == VAT_RATES
    assert Decimal(21) == DEFAULT_VAT_RATE


@pytest.mark.parametrize(
    ("scope", "kind"),
    [
        ("nacional", "business"),
        ("national", "empresa"),
        ("NATIONAL", "business"),
        ("", ""),
        (None, None),
        ("eu", "Business"),
        ("fuera_ue", "business"),
    ],
)
def test_an_unknown_scope_or_kind_is_a_programming_error(scope, kind) -> None:
    with pytest.raises(ValueError):
        invoice_terms(scope, kind)
