"""D-06 · Deducibilidad del IVA, orientativa y siempre con su motivo (SPEC-W-003 §5.1)."""

import pytest

from cuadre.validators.deductibility import EU_NOTE, deductible_vat

OWNER = "12345678Z"


@pytest.mark.parametrize(
    ("doc_type", "scope", "vat", "recipient", "owner", "expected"),
    [
        # Factura completa: deducible si es de un proveedor español con cuota.
        ("full_invoice", "national", 521, None, None, True),
        ("full_invoice", "national", 521, "OTRO", OWNER, True),  # el destinatario no importa en una factura completa
        ("full_invoice", None, 521, None, None, True),  # ámbito sin determinar: se aplica lo español
        ("full_invoice", "national", 0, None, None, False),
        ("full_invoice", "national", None, None, None, False),
        ("full_invoice", "eu", 521, None, None, False),
        # Simplificada y ticket: solo con el NIF del perfil como destinatario.
        ("simplified_invoice", "national", 694, OWNER, OWNER, True),
        ("simplified_invoice", "national", 694, "ES 12345678z", "12345678Z", True),  # normalizados antes de comparar
        ("simplified_invoice", "national", 694, "12.345.678-Z", OWNER, True),
        ("simplified_invoice", "national", 694, None, OWNER, False),
        ("simplified_invoice", "national", 694, OWNER, None, False),  # sin NIF en el perfil, nunca
        ("simplified_invoice", "national", 694, None, None, False),  # None no es igual a None
        ("simplified_invoice", "national", 694, "01230956L", OWNER, False),
        ("simplified_invoice", "national", 694, "no es un NIF", "tampoco", False),  # dos valores ilegibles no coinciden
        ("simplified_invoice", "national", 0, OWNER, OWNER, False),
        ("simplified_invoice", "eu", 694, OWNER, OWNER, False),
        ("ticket", "national", 100, OWNER, OWNER, True),
        ("ticket", "national", 100, None, OWNER, False),
        # Todo lo demás, no.
        ("receipt", "national", 521, OWNER, OWNER, False),
        ("other", "national", 521, OWNER, OWNER, False),
        ("not_an_invoice", "national", 521, OWNER, OWNER, False),
        (None, "national", 521, OWNER, OWNER, False),
    ],
)
def test_the_deductibility_matrix(
    doc_type: str | None, scope: str | None, vat: int | None, recipient: str | None, owner: str | None, expected: bool
) -> None:
    result = deductible_vat(doc_type, scope, vat, recipient, owner)  # type: ignore[arg-type]
    assert result.deductible is expected
    assert result.note, "se muestra siempre con su motivo"


def test_an_eu_supplier_is_never_deductible_and_says_why() -> None:
    result = deductible_vat("full_invoice", "eu", 1000, None, None)
    assert not result.deductible and result.note == EU_NOTE


def test_a_simplified_invoice_without_your_tax_id_explains_the_rule() -> None:
    result = deductible_vat("simplified_invoice", "national", 694, None, OWNER)
    assert result.note == "Factura simplificada: el IVA solo se deduce si lleva tu NIF."
