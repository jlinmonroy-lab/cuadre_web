"""Tipos del dominio de la emisión (SPEC-W-007 §5.1 y §5.3). Inmutables y sin lógica."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from cuadre.clients.types import Kind, Scope
from cuadre.tax.types import Amounts, InvoiceTerms, TaxTreatment

SeriesKind = Literal["standard", "rectifying"]
InvoiceKind = Literal["standard", "rectifying"]


@dataclass(frozen=True, slots=True)
class RawInvoice:
    """Lo que llega de la API, sin fiarse de nada: cada campo es `object` y un tipo inesperado es un error de campo, no una excepción."""

    client_id: object = None
    series_id: object = None
    issue_date: object = None
    concept: object = None
    base_cents: object = None
    vat_rate: object = None


@dataclass(frozen=True, slots=True)
class RawRectification:
    reason: object = None
    corrected_base_cents: object = None
    issue_date: object = None


@dataclass(frozen=True, slots=True)
class ClientCopy:
    """Lo que la factura necesita del cliente (y que luego congela): la API lo lee de la ficha; `None` si no existe o no es de la persona."""

    id: str
    name: str
    kind: Kind
    country: str
    scope: Scope
    tax_id: str | None
    address: str | None
    archived: bool


@dataclass(frozen=True, slots=True)
class SeriesInfo:
    """La serie elegida (o la predeterminada) y la fecha de su última factura emitida, si la hay."""

    id: str
    code: str
    kind: SeriesKind
    archived: bool
    last_issue_date: date | None


@dataclass(frozen=True, slots=True)
class OriginalInvoice:
    """Lo que hace falta de la factura que se rectifica. Sus condiciones (tipos, tratamiento y mención) las heredan sus rectificativas."""

    id: str
    display_number: str
    kind: InvoiceKind
    issue_date: date
    terms: InvoiceTerms
    amounts: Amounts


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class Problem:
    """Un único motivo que impide emitir aunque los campos estén bien: tiene su código estable y su estado HTTP (§5.3)."""

    code: str
    status: int
    message: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class InvoiceValues:
    """La factura validada, lista para emitirse: el cliente, la serie, la fecha, el concepto y las condiciones con sus importes."""

    client_id: str
    series_id: str
    issue_date: date
    concept: str
    terms: InvoiceTerms
    amounts: Amounts


@dataclass(frozen=True, slots=True)
class RectificationValues:
    """La rectificativa validada: sus importes son la **diferencia** (con signo) y llevan los tipos y el tratamiento de la original."""

    original_id: str
    series_id: str
    issue_date: date
    reason: str
    corrected_base_cents: int
    tax_treatment: TaxTreatment
    legal_note: str | None
    amounts: Amounts


@dataclass(frozen=True, slots=True)
class InvoiceResult:
    """O los valores, o **todos** los errores de campo a la vez, o **un** problema (nunca dos de las tres cosas)."""

    values: InvoiceValues | None
    errors: tuple[FieldError, ...] = ()
    problem: Problem | None = None


@dataclass(frozen=True, slots=True)
class RectificationResult:
    values: RectificationValues | None
    errors: tuple[FieldError, ...] = ()
    problem: Problem | None = None


@dataclass(frozen=True, slots=True)
class PdfInvoice:
    """Todo lo que el PDF de una factura dibuja, ya leído de la fila: las copias congeladas del emisor y del cliente (D-09), nunca el perfil de
    ahora. Los importes son céntimos enteros con su signo y los tipos, porcentajes (`Decimal`)."""

    display_number: str
    kind: InvoiceKind
    issue_date: date
    issuer_name: str
    issuer_tax_id: str
    issuer_address: str
    issuer_iban: str | None
    client_name: str
    client_tax_id: str | None
    client_address: str
    concept: str
    base_cents: int
    vat_rate: Decimal
    vat_cents: int
    irpf_rate: Decimal
    irpf_cents: int
    total_cents: int
    legal_note: str | None
    rectifies_number: str | None = None
    rectifies_date: date | None = None
    rectification_reason: str | None = None
