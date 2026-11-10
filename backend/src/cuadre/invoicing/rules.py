"""Validación de una factura y de una rectificativa (SPEC-W-007 §5.1.1 y §5.1.5). Python puro (T7-01, T7-04): sin base de datos, sin red y sin
reloj propio (`today` es un argumento).

Ambas funciones miran **todos** los campos y devuelven todos los errores de campo a la vez, en el orden de la pantalla (`invalid_invoice`, 422).
Si no hay ninguno, comprueban lo que impide emitir aunque los datos estén bien, y devuelven **un** problema con su código y su estado, en este
orden: cliente archivado o sin domicilio (409), retención sin elegir (422) y fecha anterior a la última de la serie (409); en una rectificativa,
primero que la original no sea ya una rectificativa y que no suba el importe. Los textos van en español y no repiten lo escrito.
"""

import unicodedata
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from cuadre.invoicing.limits import (
    BASE_MAX,
    BASE_MIN,
    CONCEPT_MAX,
    CONCEPT_MIN,
    DATE_RAW,
    FORBIDDEN_CATEGORIES,
    REASON_MAX,
    REASON_MIN,
    UUID_RAW,
)
from cuadre.invoicing.numbering import is_out_of_order
from cuadre.invoicing.rectification import standing_of
from cuadre.invoicing.texts import numeric_date
from cuadre.invoicing.types import (
    ClientCopy,
    FieldError,
    InvoiceResult,
    InvoiceValues,
    OriginalInvoice,
    Problem,
    RawInvoice,
    RawRectification,
    RectificationResult,
    RectificationValues,
    SeriesInfo,
)
from cuadre.tax import VAT_RATES, Amounts, InvoiceTerms, compute_amounts, invoice_terms, rectification_amounts
from cuadre.validators.limits import EARLIEST_DATE
from cuadre.validators.vat import parse_rate

MESSAGES = {
    "client": "Elige un cliente.",
    "client_archived": "Ese cliente está archivado: reactívalo para facturarle.",
    "client_address": "Falta el domicilio del cliente: añádelo para emitir la factura.",
    "series": "Elige una serie activa.",
    "date": "Elige la fecha de expedición.",
    "date_future": "La fecha no puede ser futura.",
    "date_order": "La fecha no puede ser anterior a la de la última factura de la serie ({fecha}).",
    "date_before_original": "La fecha no puede ser anterior a la de la factura que se rectifica ({fecha}).",
    "concept": "Describe el servicio facturado.",
    "concept_length": "El concepto admite entre 2 y 300 caracteres, sin saltos de línea.",
    "base": "Escribe un importe mayor que cero, por ejemplo 1.200,00.",
    "base_max": "El importe no puede superar 99.999.999,99 €.",
    "vat_rate": "El tipo de IVA no es válido: elige 21, 10 o 4 %.",
    "vat_not_applicable": "Este cliente no lleva IVA: no envíes tipo de IVA.",
    "irpf_rate_missing": "Elige tu retención de IRPF en el perfil para facturar a una empresa.",
    "reason": "Escribe el motivo de la rectificación.",
    "reason_length": "El motivo admite entre 2 y 300 caracteres, sin saltos de línea.",
    "corrected_base": "Escribe la base corregida (0 si se anula la factura).",
    "corrected_nothing": "La base corregida es igual a la actual: no hay nada que rectificar.",
    "rectification_exceeds": "Una rectificativa no puede subir el importe: emite una factura nueva.",
    "not_rectifiable": "Una factura rectificativa no se puede rectificar: rectifica la original.",
}


def parse_uuid(raw: object) -> str | None:
    """Un UUID escrito de cualquier forma habitual, en minúsculas; `None` si no lo es (la API no consulta la base con basura)."""
    if not isinstance(raw, str):
        return None
    text = raw.strip().lower()
    return text if UUID_RAW.fullmatch(text) is not None else None


# --- Campos ---------------------------------------------------------------------------------------------------------------------


def _text(raw: object, low: int, high: int, missing: str, length: str) -> tuple[str | None, str | None]:
    """Texto de una línea de `low` a `high` caracteres, recortado. Un tipo que no es texto o un texto vacío es «falta»; los controles y las
    longitudes, el mensaje de longitud."""
    if not isinstance(raw, str):
        return None, missing
    text = raw.strip()
    if not text:
        return None, missing
    if any(unicodedata.category(ch) in FORBIDDEN_CATEGORIES for ch in text):
        return None, length
    if not low <= len(text) <= high:
        return None, length
    return text, None


def _date(raw: object) -> date | None:
    """`AAAA-MM-DD` real (el prefiltro ASCII va antes de `date`) o un `date`; antes del 2000 no se admite."""
    if type(raw) is date:
        value = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if DATE_RAW.fullmatch(text) is None:
            return None
        try:
            value = date(int(text[:4]), int(text[5:7]), int(text[8:10]))
        except ValueError:
            return None
    else:
        return None
    return value if value >= EARLIEST_DATE else None


def _issue_date(raw: object, today: date) -> tuple[date | None, str | None]:
    value = _date(raw)
    if value is None:
        return None, MESSAGES["date"]
    if value > today:
        return None, MESSAGES["date_future"]
    return value, None


def _base(raw: object) -> tuple[int | None, str | None]:
    """Un entero (`bool` no lo es) de `BASE_MIN` a `BASE_MAX` céntimos."""
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < BASE_MIN:
        return None, MESSAGES["base"]
    if raw > BASE_MAX:
        return None, MESSAGES["base_max"]
    return raw, None


def _vat(raw: object, terms: InvoiceTerms | None) -> tuple[Decimal | None, str | None]:
    """Vacío = el del tratamiento. Un tipo es 21, 10 o 4 (`21`, `21.0` y `21.00` son el mismo); a un cliente sin IVA no se le envía ninguno."""
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, MESSAGES["vat_rate"]
    text = raw.strip()
    if not text:
        return None, None
    rate = parse_rate(text)
    if rate is None or rate not in VAT_RATES:
        return None, MESSAGES["vat_rate"]
    if terms is not None and not terms.vat_editable:
        return None, MESSAGES["vat_not_applicable"]
    return rate, None


def _series(series: SeriesInfo | None) -> str | None:
    """Solo se factura en una serie ordinaria y activa (la rectificativa es de las rectificativas)."""
    if series is None or series.archived or series.kind != "standard":
        return MESSAGES["series"]
    return None


# --- Factura --------------------------------------------------------------------------------------------------------------------


def validate_invoice(
    raw: RawInvoice,
    *,
    client: ClientCopy | None,
    series: SeriesInfo | None,
    irpf_rate: Decimal | None,
    today: date,
) -> InvoiceResult:
    """Valida una factura ordinaria. `client` y `series` los resuelve la API (`None` si no existen, no son de la persona o no se eligieron);
    `irpf_rate` es la retención del perfil. Devuelve los valores con sus importes, todos los errores de campo, o un problema."""
    terms = invoice_terms(client.scope, client.kind) if client is not None else None
    issue_date, e_date = _issue_date(raw.issue_date, today)
    concept, e_concept = _text(raw.concept, CONCEPT_MIN, CONCEPT_MAX, MESSAGES["concept"], MESSAGES["concept_length"])
    base, e_base = _base(raw.base_cents)
    vat, e_vat = _vat(raw.vat_rate, terms)
    pairs = (
        ("client_id", None if client is not None else MESSAGES["client"]),
        ("series_id", _series(series)),
        ("issue_date", e_date),
        ("concept", e_concept),
        ("base_cents", e_base),
        ("vat_rate", e_vat),
    )
    errors = tuple(FieldError(field, message) for field, message in pairs if message is not None)
    if errors:
        return InvoiceResult(None, errors)
    assert client is not None and series is not None and terms is not None
    assert issue_date is not None and concept is not None and base is not None

    if client.archived:
        return _blocked("client_not_billable", 409, MESSAGES["client_archived"], "client_id")
    if client.address is None or not client.address.strip():
        return _blocked("client_not_billable", 409, MESSAGES["client_address"], "address")
    if terms.withholds and irpf_rate is None:
        return _blocked("irpf_rate_missing", 422, MESSAGES["irpf_rate_missing"], None)
    if is_out_of_order(issue_date, series.last_issue_date):
        assert series.last_issue_date is not None
        message = MESSAGES["date_order"].format(fecha=numeric_date(series.last_issue_date))
        return _blocked("invoice_date_out_of_order", 409, message, "issue_date")

    amounts = compute_amounts(terms, base, vat, irpf_rate)
    return InvoiceResult(InvoiceValues(client.id, series.id, issue_date, concept, terms, amounts))


def _blocked(code: str, status: int, message: str, field: str | None) -> InvoiceResult:
    return InvoiceResult(None, (), Problem(code, status, message, field))


# --- Rectificativa --------------------------------------------------------------------------------------------------------------


def _corrected(raw: object, current_base: int) -> tuple[int | None, str | None]:
    """La base corregida: un entero de 0 a `BASE_MAX` y distinto de la vigente (con la misma no hay nada que rectificar)."""
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 or raw > BASE_MAX:
        return None, MESSAGES["corrected_base"]
    if raw == current_base:
        return None, MESSAGES["corrected_nothing"]
    return raw, None


def validate_rectification(
    raw: RawRectification,
    *,
    original: OriginalInvoice,
    rectifications: Sequence[Amounts],
    series: SeriesInfo,
    today: date,
) -> RectificationResult:
    """Valida una rectificativa por diferencia de valores (art. 15.4 y 15.5 del Reglamento). `rectifications` son los importes de las que ya
    tiene la original y `series` es la serie rectificativa del año (un `ValueError` si no lo es: la API la elige, la persona no)."""
    if series.kind != "rectifying" or series.archived:
        raise ValueError("La serie de una rectificativa es la rectificativa del año y está activa.")
    if original.kind != "standard":
        return RectificationResult(None, (), Problem("invoice_not_rectifiable", 409, MESSAGES["not_rectifiable"]))

    standing = standing_of(original.amounts, rectifications)
    reason, e_reason = _text(raw.reason, REASON_MIN, REASON_MAX, MESSAGES["reason"], MESSAGES["reason_length"])
    corrected, e_corrected = _corrected(raw.corrected_base_cents, standing.base_cents)
    issue_date, e_date = _issue_date(raw.issue_date, today)
    pairs = (("reason", e_reason), ("corrected_base_cents", e_corrected), ("issue_date", e_date))
    errors = tuple(FieldError(field, message) for field, message in pairs if message is not None)
    if errors:
        return RectificationResult(None, errors)
    assert reason is not None and corrected is not None and issue_date is not None

    if corrected > standing.base_cents:
        return RectificationResult(
            None, (), Problem("rectification_exceeds", 409, MESSAGES["rectification_exceeds"], "corrected_base_cents")
        )
    if issue_date < original.issue_date:
        message = MESSAGES["date_before_original"].format(fecha=numeric_date(original.issue_date))
        return RectificationResult(None, (), Problem("invoice_date_out_of_order", 409, message, "issue_date"))
    if is_out_of_order(issue_date, series.last_issue_date):
        assert series.last_issue_date is not None
        message = MESSAGES["date_order"].format(fecha=numeric_date(series.last_issue_date))
        return RectificationResult(None, (), Problem("invoice_date_out_of_order", 409, message, "issue_date"))

    amounts = rectification_amounts(standing, original.amounts.vat_rate, original.amounts.irpf_rate, corrected)
    values = RectificationValues(
        original.id,
        series.id,
        issue_date,
        reason,
        corrected,
        original.terms.treatment,
        original.terms.legal_note,
        amounts,
    )
    return RectificationResult(values)
