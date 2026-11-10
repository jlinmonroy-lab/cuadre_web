"""Tipos del dominio fiscal de la emisión (SPEC-W-007 §5.1.2 y §5.1.3). Inmutables y sin lógica."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

TaxTreatment = Literal[
    "national_vat", "eu_reverse_charge", "eu_consumer_vat", "non_eu_consumer_vat", "non_eu_not_subject"
]


@dataclass(frozen=True, slots=True)
class InvoiceTerms:
    """Lo que el ámbito y el tipo del cliente deciden: el tratamiento fiscal (que se guarda en la factura), si el IVA se puede elegir y con
    qué tipo por defecto (`0` si no lleva IVA), si lleva retención de IRPF y la mención legal."""

    treatment: TaxTreatment
    vat_editable: bool
    vat_rate: Decimal
    withholds: bool
    legal_note: str | None


@dataclass(frozen=True, slots=True)
class Amounts:
    """Importes en céntimos enteros (con signo en una rectificativa) y tipos con dos decimales. `total = base + IVA − retención`."""

    base_cents: int
    vat_rate: Decimal
    vat_cents: int
    irpf_rate: Decimal
    irpf_cents: int
    total_cents: int


@dataclass(frozen=True, slots=True)
class Standing:
    """Lo vigente de una factura: la base, el IVA y la retención de la original más lo que suman sus rectificativas."""

    base_cents: int
    vat_cents: int
    irpf_cents: int
