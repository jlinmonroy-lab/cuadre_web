"""Ayudas de las pruebas de facturas (SPEC-W-007 hito 2): una persona lista para emitir, clientes de cada ámbito y las condiciones que calcula
`cuadre.tax`. Las pruebas llaman a las funciones `app.*` con condiciones calculadas por el dominio de verdad (no escritas a mano): así se ve que
las dos mitades encajan."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.tax import Standing, compute_amounts, invoice_terms, rectification_amounts
from tests.support import Outcome, Person, Pool, call

D1 = date(2026, 3, 2)
D2 = date(2026, 3, 9)
D3 = date(2026, 3, 16)
D4 = date(2026, 3, 23)

ISSUER = {
    "legal_name": "Emisor Sintético",
    "tax_id": "12345678Z",
    "fiscal_address": "Calle Emisor 1, 00000 Ciudad de Pruebas",
    "iban": "ES3600000000050000000001",
}


def prepare(admin: Connection[DictRow], person: Person, *, irpf: str | None = "15.00", **profile: Any) -> uuid.UUID:
    """Completa el perfil de `person` y le crea la serie `2026`, predeterminada. Devuelve el id de la serie."""
    values = {**ISSUER, "irpf_rate": irpf, **profile}
    admin.execute(
        "update public.business_profiles set legal_name = %(legal_name)s, tax_id = %(tax_id)s, fiscal_address = %(fiscal_address)s, "
        "iban = %(iban)s, irpf_rate = %(irpf_rate)s where owner_id = %(owner)s",
        {**values, "owner": person.id},
    )
    return series(admin, person, "2026", default=True)


def series(
    admin: Connection[DictRow],
    person: Person,
    code: str,
    *,
    default: bool = False,
    kind: str = "standard",
    first: int = 1,
) -> uuid.UUID:
    row = admin.execute(
        "insert into public.invoice_series (owner_id, code, kind, is_default, first_number, next_number) "
        "values (%s, %s, %s, %s, %s, %s) returning id",
        (person.id, code, kind, default, first, first),
    ).fetchone()
    assert row is not None
    return row["id"]


def client(
    admin: Connection[DictRow],
    person: Person,
    scope: str = "national",
    kind: str = "business",
    *,
    name: str | None = None,
    address: str | None = "Calle del Cliente 3, Madrid",
    archived: bool = False,
) -> uuid.UUID:
    country = {"national": "ES", "eu": "DE", "non_eu": "MX"}[scope]
    row = admin.execute(
        "insert into public.clients (owner_id, name, kind, country, scope, tax_id, address, archived_at) "
        "values (%s, %s, %s, %s, %s, %s, %s, case when %s then now() end) returning id",
        (
            person.id,
            name or f"Cliente {scope} {kind} {uuid.uuid4().hex[:6]}",
            kind,
            country,
            scope,
            f"X{uuid.uuid4().hex[:8].upper()}" if kind == "business" else None,
            address,
            archived,
        ),
    ).fetchone()
    assert row is not None
    return row["id"]


def terms(
    scope: str = "national",
    kind: str = "business",
    base: int = 100_000,
    *,
    vat: str | None = None,
    irpf: str | None = "15",
) -> dict[str, Any]:
    """Las condiciones de una factura al cliente de ese ámbito y tipo, tal como las calcula `cuadre.tax`."""
    t = invoice_terms(scope, kind)  # type: ignore[arg-type]
    a = compute_amounts(t, base, Decimal(vat) if vat else None, Decimal(irpf) if irpf else None)
    return {
        "tax_treatment": t.treatment,
        "vat_rate": int(a.vat_rate),
        "vat_cents": a.vat_cents,
        "irpf_rate": int(a.irpf_rate),
        "irpf_cents": a.irpf_cents,
        "total_cents": a.total_cents,
        "legal_note": t.legal_note,
    }


def rectification_terms(standing: Standing, corrected: int, *, vat: str = "21", irpf: str = "15") -> dict[str, int]:
    a = rectification_amounts(standing, Decimal(vat), Decimal(irpf), corrected)
    return {"vat_cents": a.vat_cents, "irpf_cents": a.irpf_cents, "total_cents": a.total_cents}


def issue(
    pool: Pool,
    person: Person,
    client_id: object,
    series_id: object,
    *,
    when: date | None = D1,
    concept: str | None = "Servicios de diseño",
    base: int | None = 100_000,
    given: Any = "default",
    scope: str = "national",
    kind: str = "business",
    vat: str | None = None,
    irpf: str | None = "15",
) -> Outcome:
    """Llama a `app.issue_invoice`. Sin `given`, las condiciones son las del dominio para ese ámbito y tipo de cliente."""
    t = terms(scope, kind, base or 100_000, vat=vat, irpf=irpf) if given == "default" else given
    return call(
        pool, person, "issue_invoice", client_id, series_id, when, concept, base, Jsonb(t) if t is not None else None
    )


def rectify(
    pool: Pool,
    person: Person,
    original: object,
    *,
    corrected: int | None = 80_000,
    when: date | None = D2,
    reason: str | None = "Importe mal calculado",
    given: Any = "default",
    standing: Standing | None = None,
    vat: str = "21",
    irpf: str = "15",
) -> Outcome:
    """Llama a `app.issue_rectifying_invoice`. Sin `given`, las condiciones salen de `rectification_amounts` desde lo vigente que se indique
    (por defecto una factura de base 100.000 al 21 % con retención del 15 %)."""
    base = standing or Standing(100_000, 21_000, 15_000)
    if given == "default":
        given = rectification_terms(base, corrected or 0, vat=vat, irpf=irpf)
    return call(
        pool,
        person,
        "issue_rectifying_invoice",
        original,
        reason,
        corrected,
        when,
        Jsonb(given) if given is not None else None,
    )


@dataclass
class Ready:
    """Alicia lista para emitir: la serie `2026` y un cliente de cada ámbito y tipo."""

    series: uuid.UUID
    clients: dict[tuple[str, str], uuid.UUID]


def ready(admin: Connection[DictRow], person: Person, **profile: Any) -> Ready:
    serie = prepare(admin, person, **profile)
    clients = {
        (scope, kind): client(admin, person, scope, kind)
        for scope in ("national", "eu", "non_eu")
        for kind in ("business", "individual")
    }
    return Ready(serie, clients)


def today(admin: Connection[DictRow]) -> date:
    """Hoy en Europe/Madrid, como lo ve la base de datos."""
    row = admin.execute("select private.today_madrid() as d").fetchone()
    assert row is not None
    return row["d"]


def made(out: Outcome) -> uuid.UUID:
    assert not out.error, out.message
    return next(iter(out.rows[0].values()))


def code_of(out: Outcome) -> str:
    """El código estable del error (`client_not_found`…): es el mensaje de la excepción."""
    assert out.sqlstate == "P0001", (out.sqlstate, out.message)
    return (out.message or "").strip()


def invoice(admin: Connection[DictRow], invoice_id: object) -> dict[str, Any]:
    row = admin.execute("select * from public.invoices where id = %s", (invoice_id,)).fetchone()
    assert row is not None
    return row


def next_number(admin: Connection[DictRow], series_id: object) -> int:
    row = admin.execute("select next_number from public.invoice_series where id = %s", (series_id,)).fetchone()
    assert row is not None
    return row["next_number"]


def insert_direct(
    admin: Connection[DictRow], person: Person, series_id: object, client_id: object, **fields: Any
) -> uuid.UUID:
    """Inserta una factura ordinaria válida como dueño de la base de datos (salta las funciones: para probar la tabla)."""
    values: dict[str, Any] = {
        "owner_id": person.id,
        "series_id": series_id,
        "series_code": "2026",
        "number": 1,
        "kind": "standard",
        "issue_date": D1,
        "client_id": client_id,
        "client_name": "Cliente Directo S.L.",
        "client_kind": "business",
        "client_country": "ES",
        "client_scope": "national",
        "client_address": "Calle del Cliente 3, Madrid",
        "issuer_name": "Emisor Sintético",
        "issuer_tax_id": "12345678Z",
        "issuer_address": "Calle Emisor 1, 00000 Ciudad de Pruebas",
        "concept": "Concepto directo",
        "tax_treatment": "national_vat",
        "base_cents": 1000,
        "total_cents": 1000,
        **fields,
    }
    row = admin.execute(
        f"insert into public.invoices ({', '.join(values)}) values ({', '.join(['%s'] * len(values))}) returning id",
        tuple(values.values()),
    ).fetchone()
    assert row is not None
    return row["id"]
