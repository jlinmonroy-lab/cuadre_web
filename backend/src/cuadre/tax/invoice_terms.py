"""Condiciones fiscales por ámbito y tipo del cliente (SPEC-W-007 §5.1.2, D-05). Python puro.

| Cliente | Tratamiento | IVA | Retención | Mención |
|---|---|---|---|---|
| Nacional, empresa | `national_vat` | 21 % (21, 10 o 4) | la del perfil | — |
| Nacional, particular | `national_vat` | 21 % (21, 10 o 4) | ninguna | — |
| UE, empresa | `eu_reverse_charge` | sin IVA | ninguna | Inversión del sujeto pasivo |
| UE, particular | `eu_consumer_vat` | 21 % (IVA español) | ninguna | — |
| Fuera de la UE, empresa | `non_eu_not_subject` | sin IVA | ninguna | art. 69 de la Ley del IVA |
| Fuera de la UE, particular | `non_eu_consumer_vat` | 21 % (IVA español) | ninguna | — |
"""

from decimal import Decimal

from cuadre.clients.types import Kind, Scope
from cuadre.tax.limits import DEFAULT_VAT_RATE, NOTE_NON_EU, NOTE_REVERSE_CHARGE
from cuadre.tax.types import InvoiceTerms

_NO_VAT = Decimal(0)

_TERMS: dict[tuple[Scope, Kind], InvoiceTerms] = {
    ("national", "business"): InvoiceTerms("national_vat", True, DEFAULT_VAT_RATE, True, None),
    ("national", "individual"): InvoiceTerms("national_vat", True, DEFAULT_VAT_RATE, False, None),
    ("eu", "business"): InvoiceTerms("eu_reverse_charge", False, _NO_VAT, False, NOTE_REVERSE_CHARGE),
    ("eu", "individual"): InvoiceTerms("eu_consumer_vat", True, DEFAULT_VAT_RATE, False, None),
    ("non_eu", "business"): InvoiceTerms("non_eu_not_subject", False, _NO_VAT, False, NOTE_NON_EU),
    ("non_eu", "individual"): InvoiceTerms("non_eu_consumer_vat", True, DEFAULT_VAT_RATE, False, None),
}


def invoice_terms(scope: Scope, kind: Kind) -> InvoiceTerms:
    """Las condiciones de una factura a un cliente de ese ámbito y tipo. Un valor que no es de la tabla es un error de programación."""
    try:
        return _TERMS[(scope, kind)]
    except KeyError:
        raise ValueError(f"Ámbito o tipo de cliente desconocido: {scope!r}, {kind!r}") from None
