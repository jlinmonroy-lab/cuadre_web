"""Normalización de la lectura de una factura (SPEC-W-002 §5.3, T2-05, RES-02).

La respuesta del agente es entrada no confiable. Esta es la única forma en que entra a la base de datos: importes en céntimos
enteros (nunca `float`), textos acotados y limpios, listas con tope. Si algo no cumple, se rechaza la respuesta **entera**
(`invalid_response`) y no se guarda nada de ella.

Los modelos de `cuadre_contracts` ya validan la forma; aquí se vuelve a comprobar a propósito (doble cerco), porque este módulo es
lo que protege a la base de datos aunque un cliente futuro se salte la validación.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from cuadre.agents.errors import LIMIT_TRACE_ID, AgentsError, FailureCode
from cuadre.agents.text import InvalidText, clean_text
from cuadre_contracts import ExtractResponse
from cuadre_contracts.extract import DocType, DoubtReason, ExtractedField

# `\d` casa dígitos de cualquier alfabeto y `$` admite un salto de línea final: por eso, rangos ASCII y `fullmatch`.
AMOUNT = re.compile(r"-?[0-9]{1,12}\.[0-9]{2}")
RATE = re.compile(r"[0-9]{1,3}(\.[0-9]{1,2})?")
COST = re.compile(r"[0-9]{1,6}\.[0-9]{2,6}")
CURRENCY = re.compile(r"[A-Z]{3}")

MAX_TAX_LINES = 10
MAX_DOUBTFUL_FIELDS = 50
MAX_WARNINGS = 5
MAX_COST_EUR = Decimal("1000")  # `documents.agent_cost_eur` es numeric(9, 6): no admite 1000 ni más

LIMIT_NAME = 200
LIMIT_TAX_ID = 32
LIMIT_INVOICE_NUMBER = 64
LIMIT_RAW_TEXT = 200
LIMIT_WARNING = 300


class _Invalid(Exception):
    """Interna: algo de la respuesta no cumple. `normalize_extraction` la convierte en `invalid_response`."""


@dataclass(frozen=True)
class NormalizedReading:
    """Lo que se guarda de una lectura: `extraction` va a `documents.extraction`; el resto, a sus columnas."""

    extraction: dict[str, Any]
    injection_suspected: bool
    trace_id: str | None
    cost_eur: Decimal | None


def to_cents(value: str | None) -> int | None:
    """`"120.00"` → 12000. Cualquier cadena que no sea un importe con punto y dos decimales invalida la respuesta."""
    if value is None:
        return None
    if not isinstance(value, str) or AMOUNT.fullmatch(value) is None:
        raise _Invalid
    return int(Decimal(value) * 100)


def to_rate(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or RATE.fullmatch(value) is None:
        raise _Invalid
    return value


def to_cost(value: str | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str) or COST.fullmatch(value) is None:
        raise _Invalid
    cost = Decimal(value)
    if cost >= MAX_COST_EUR:
        raise _Invalid
    return cost


def _enum_value(enum_type: type[DocType] | type[ExtractedField] | type[DoubtReason], value: object) -> str:
    try:
        return enum_type(value).value
    except ValueError:
        raise _Invalid from None


def normalize_extraction(response: ExtractResponse) -> NormalizedReading:
    """Respuesta del agente → forma guardada. Lanza `AgentsError(invalid_response)` si algo no cumple."""
    try:
        trace_id = clean_text(response.trace_id, LIMIT_TRACE_ID)
    except InvalidText:
        trace_id = None
    try:
        return _normalize(response, trace_id)
    except (_Invalid, InvalidText):
        # `from None`: el contexto de la excepción podría arrastrar datos recibidos (NFR-11).
        raise AgentsError(FailureCode.invalid_response, trace_id=trace_id) from None


def _normalize(response: ExtractResponse, trace_id: str | None) -> NormalizedReading:
    e = response.extraction
    if len(e.tax_breakdown) > MAX_TAX_LINES or len(e.doubtful_fields) > MAX_DOUBTFUL_FIELDS:
        raise _Invalid

    if not isinstance(e.injection_suspected, bool):
        raise _Invalid
    issue_date = e.issue_date
    if issue_date is not None and (not isinstance(issue_date, date) or isinstance(issue_date, datetime)):
        raise _Invalid
    currency = e.currency
    if currency is not None and (not isinstance(currency, str) or CURRENCY.fullmatch(currency) is None):
        raise _Invalid

    tax_breakdown = [
        {"vat_rate": to_rate(line.vat_rate), "base_cents": to_cents(line.base), "vat_cents": to_cents(line.vat_amount)}
        for line in e.tax_breakdown
    ]
    withholding = (
        None
        if e.withholding is None
        else {"rate": to_rate(e.withholding.rate), "amount_cents": to_cents(e.withholding.amount)}
    )

    doubtful_fields = []
    for doubt in e.doubtful_fields:
        index = doubt.line_index
        if index is not None and not (isinstance(index, int) and not isinstance(index, bool) and index >= 0):
            raise _Invalid
        doubtful_fields.append(
            {
                "field": _enum_value(ExtractedField, doubt.field),
                # Una duda que apunta a una línea que no existe se queda en el campo: no se descarta, pero no se indexa fuera.
                "line_index": index if index is not None and index < len(tax_breakdown) else None,
                "reason": _enum_value(DoubtReason, doubt.reason),
                "raw_text": clean_text(doubt.raw_text, LIMIT_RAW_TEXT),
            }
        )

    cleaned_warnings = (clean_text(w, LIMIT_WARNING) for w in e.warnings)
    warnings = [w for w in cleaned_warnings if w is not None][:MAX_WARNINGS]

    extraction: dict[str, Any] = {
        "doc_type": _enum_value(DocType, e.doc_type),
        "supplier_name": clean_text(e.supplier_name, LIMIT_NAME),
        "supplier_tax_id": clean_text(e.supplier_tax_id, LIMIT_TAX_ID),
        "recipient_tax_id": clean_text(e.recipient_tax_id, LIMIT_TAX_ID),
        "invoice_number": clean_text(e.invoice_number, LIMIT_INVOICE_NUMBER),
        "issue_date": issue_date.isoformat() if issue_date is not None else None,
        "currency": currency,
        "tax_breakdown": tax_breakdown,
        "withholding": withholding,
        "total_cents": to_cents(e.total),
        "doubtful_fields": doubtful_fields,
        "warnings": warnings,
    }
    return NormalizedReading(
        extraction=extraction,
        injection_suspected=e.injection_suspected,
        trace_id=trace_id,
        cost_eur=to_cost(response.usage.cost_eur),
    )
