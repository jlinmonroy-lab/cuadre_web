"""Tipos del cierre mensual (SPEC-W-012 §5.1 y §5.4). Inmutables y sin lógica, salvo el calendario de `YearMonth`.

El ámbito se redefine aquí (`national | eu | non_eu`, los de `public.client_scope`) para que este módulo puro no importe el paquete de clientes.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, NamedTuple

Scope = Literal["national", "eu", "non_eu"]
InvoiceKind = Literal["standard", "rectifying"]
SCOPES: tuple[Scope, ...] = ("national", "eu", "non_eu")
KINDS: tuple[InvoiceKind, ...] = ("standard", "rectifying")


class YearMonth(NamedTuple):
    """Un mes de calendario. Compara y ordena como la tupla `(año, mes)`."""

    year: int
    month: int

    @classmethod
    def of(cls, day: date) -> "YearMonth":
        return cls(day.year, day.month)

    def shift(self, months: int) -> "YearMonth":
        index = self.year * 12 + (self.month - 1) + months
        return YearMonth(index // 12, index % 12 + 1)

    def previous(self) -> "YearMonth":
        return self.shift(-1)

    def next(self) -> "YearMonth":
        return self.shift(1)

    @property
    def label(self) -> str:
        """`2026-09`: la clave del mes en los registros."""
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True, slots=True)
class MonthInvoice:
    """Una factura emitida. `base_cents` lleva signo: una rectificativa lleva la diferencia. `client_name` y `scope` son los de la factura, no los actuales del cliente."""

    id: str
    issue_date: date
    kind: InvoiceKind
    base_cents: int
    client_id: str
    client_name: str
    scope: Scope


@dataclass(frozen=True, slots=True)
class MonthExpense:
    """Un gasto registrado, con factura o sin ella (los manuales no llevan IVA). `voided` es `voided_at is not null`."""

    id: str
    expense_date: date
    base_cents: int
    vat_cents: int
    deductible_vat: bool
    voided: bool


@dataclass(frozen=True, slots=True)
class ClientTotals:
    """Lo facturado a un cliente en un ámbito durante el mes. `invoice_count` cuenta solo las facturas ordinarias (puede ser 0 si solo hay rectificativas)."""

    client_id: str
    name: str
    scope: Scope
    base_cents: int
    invoice_count: int


@dataclass(frozen=True, slots=True)
class MonthTotals:
    """La foto de un mes. `total_cents = national_cents + eu_cents + non_eu_cents`; el desglose suma cada ámbito y las facturas ordinarias."""

    year: int
    month: int
    invoice_count: int
    national_cents: int
    eu_cents: int
    non_eu_cents: int
    total_cents: int
    expenses_cents: int
    by_client: tuple[ClientTotals, ...]
