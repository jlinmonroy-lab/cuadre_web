"""Datos sintéticos y ayudantes de las pruebas de facturación (RES-07). Ningún reloj: `TODAY` es el día de hoy de todas las pruebas."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from cuadre.invoicing import (
    ClientCopy,
    OriginalInvoice,
    RawInvoice,
    RawRectification,
    SeriesInfo,
    display_number,
    validate_invoice,
)
from cuadre.tax import invoice_terms

TODAY = date(2026, 11, 10)
CLIENT_ID = "0b6e2a9c-3f4d-4e1a-9c7b-5d8a1f2e3c4b"
SERIES_ID = "5c1f3d2e-8a7b-4c6d-9e0f-1a2b3c4d5e6f"
RECT_SERIES_ID = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a"
ORIGINAL_ID = "11111111-2222-4333-8444-555555555555"
IRPF = Decimal(15)

LF, TAB, NUL = chr(10), chr(9), chr(0)
ZERO_WIDTH = chr(0x200B)
RLO = chr(0x202E)
LINE_SEP = chr(0x2028)
NBSP = chr(0xA0)
FULLWIDTH_DATE = "".join(chr(0xFF10 + int(c)) if c.isdigit() else c for c in "2026-11-10")


def client(scope: str = "national", kind: str = "business", **changes: object) -> ClientCopy:
    base = ClientCopy(
        CLIENT_ID, "Estudio Norte S.L.", kind, "ES", scope, "B00000018", "Avenida Imaginaria 22, 08001 Barcelona", False
    )  # type: ignore[arg-type]
    return replace(base, **changes)  # type: ignore[arg-type]


def series(**changes: object) -> SeriesInfo:
    return replace(SeriesInfo(SERIES_ID, "2026", "standard", False, None), **changes)  # type: ignore[arg-type]


def rect_series(**changes: object) -> SeriesInfo:
    return replace(SeriesInfo(RECT_SERIES_ID, "R-2026", "rectifying", False, None), **changes)  # type: ignore[arg-type]


def raw(**changes: object) -> RawInvoice:
    base = RawInvoice(CLIENT_ID, SERIES_ID, "2026-11-10", "Diseño de identidad visual", 120_000, None)
    return replace(base, **changes)


def raw_rectification(**changes: object) -> RawRectification:
    return replace(RawRectification("Importe corregido", 100_000, "2026-11-10"), **changes)


def issue(
    *,
    cl: ClientCopy | None = None,
    se: SeriesInfo | None = None,
    irpf: Decimal | None = IRPF,
    today: date = TODAY,
    **fields: object,
):
    """`validate_invoice` con los valores por defecto de las pruebas; `cl=None` no significa «sin cliente»: usa `client()`."""
    return validate_invoice(
        raw(**fields),
        client=cl if cl is not None else client(),
        series=se if se is not None else series(),
        irpf_rate=irpf,
        today=today,
    )


def issue_no_client(**fields: object):
    return validate_invoice(raw(**fields), client=None, series=series(), irpf_rate=IRPF, today=TODAY)


def issue_no_series(**fields: object):
    return validate_invoice(raw(**fields), client=client(), series=None, irpf_rate=IRPF, today=TODAY)


def original(
    scope: str = "national",
    client_kind: str = "business",
    base: int = 120_000,
    vat: Decimal | None = None,
    irpf: Decimal | None = IRPF,
    **changes: object,
) -> OriginalInvoice:
    """Una factura ordinaria ya emitida, a partir de `validate_invoice` (así lleva sus condiciones e importes reales)."""
    result = issue(
        cl=client(scope, client_kind), irpf=irpf, base_cents=base, vat_rate=None if vat is None else str(vat)
    )
    assert result.values is not None, result
    values = result.values
    built = OriginalInvoice(
        ORIGINAL_ID, display_number("2026", 14), "standard", date(2026, 11, 3), values.terms, values.amounts
    )
    return replace(built, **changes)  # type: ignore[arg-type]


def terms_of(scope: str, kind: str):
    return invoice_terms(scope, kind)  # type: ignore[arg-type]
