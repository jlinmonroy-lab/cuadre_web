"""SQL de facturas (SQL explícito, sin ORM; ADR-0003). Toda escritura pasa por las funciones `app.*` del hito 2.

Las funciones reciben una conexión que ya lleva la identidad de la persona (`user_transaction`). `translate_db_error` traduce los errores con código
estable de §5.2 («Para el hito 3» del Anexo B.3); lo que no se reconoce se propaga y la API lo responde como un 500 sin detalles: son errores de
construcción (`terms`, `tax_treatment`, `vat_rate`…) o de base que la validación previa debería haber impedido.

Las condiciones viajan a la base como `Jsonb` con **enteros** JSON para los tipos de IVA y de retención y para los importes (la base los exige así).
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError, forbidden
from cuadre.invoicing import errors
from cuadre.invoicing.rules import MESSAGES
from cuadre.invoicing.types import FieldError, InvoiceValues, Problem, RectificationValues
from cuadre.profile.rules import LABELS

# Las columnas de una factura con lo que hace falta para `Invoice`: la copia del cliente, la original a la que rectifica, si tiene PDF y, en una
# ordinaria, lo vigente (la suma de ella y de sus rectificativas).
INVOICE_SELECT = """
SELECT i.id, i.series_code, i.number, i.kind::text AS kind, i.issue_date,
       i.issuer_name, i.issuer_tax_id, i.issuer_address, i.issuer_iban,
       i.client_id, i.client_name, i.client_kind::text AS client_kind, i.client_country, i.client_scope::text AS client_scope,
       i.client_tax_id, i.client_address, i.concept, i.tax_treatment::text AS tax_treatment,
       i.base_cents, i.vat_rate, i.vat_cents, i.irpf_rate, i.irpf_cents, i.total_cents, i.legal_note,
       i.rectifies_id, o.series_code AS original_series_code, o.number AS original_number, o.issue_date AS original_issue_date,
       i.rectification_reason, i.paid_at, i.created_at,
       EXISTS (SELECT 1 FROM public.invoice_files f WHERE f.invoice_id = i.id) AS has_pdf,
       CASE WHEN i.kind = 'standard' THEN i.base_cents + COALESCE((SELECT sum(r.base_cents) FROM public.invoices r WHERE r.rectifies_id = i.id), 0) END
           AS standing_base,
       CASE WHEN i.kind = 'standard' THEN i.vat_cents + COALESCE((SELECT sum(r.vat_cents) FROM public.invoices r WHERE r.rectifies_id = i.id), 0) END
           AS standing_vat,
       CASE WHEN i.kind = 'standard' THEN i.irpf_cents + COALESCE((SELECT sum(r.irpf_cents) FROM public.invoices r WHERE r.rectifies_id = i.id), 0) END
           AS standing_irpf
  FROM public.invoices i
  LEFT JOIN public.invoices o ON o.id = i.rectifies_id
"""
_OWN = "i.owner_id = (SELECT private.read_owner())"

_PLAIN = {
    "invoice_not_found": errors.invoice_not_found,
    "invoice_not_payable": errors.invoice_not_payable,
    "series_exhausted": errors.series_exhausted,
}
# Campos de `invalid_invoice` que la persona puede ver: los demás (`terms`, `tax_treatment`, `vat_rate`…) son un error de construcción nuestro.
_FIELDS = {"issue_date": "date", "concept": "concept_length", "base_cents": "base"}
# `invalid_invoice` y `rectification_exceeds` en una rectificativa significan que lo vigente cambió entre la lectura y el cerrojo.
_STALE_FIELDS = {"corrected_base_cents", "vat_cents", "irpf_cents", "total_cents"}


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` -> problem+json. `None` si no es uno de ellos (se propaga: 500)."""
    if exc.sqlstate == "42501":
        return forbidden()
    if exc.sqlstate != "P0001":
        return None
    message = exc.diag.message_primary or ""
    detail = (exc.diag.message_detail or "").strip()
    factory = _PLAIN.get(message)
    if factory is not None:
        return factory()
    if message == "client_not_found":
        return errors.invalid_invoice((FieldError("client_id", MESSAGES["client"]),))
    if message == "series_not_found":
        return errors.invalid_invoice((FieldError("series_id", MESSAGES["series"]),))
    if message == "client_not_billable":
        return errors.not_billable(detail)
    if message == "profile_incomplete":
        return errors.profile_incomplete([(f, LABELS[f]) for f in detail.split(",") if f in LABELS])
    if message == "irpf_rate_missing":
        return errors.from_problem(Problem("irpf_rate_missing", 422, MESSAGES["irpf_rate_missing"]))
    if message == "invoice_date_out_of_order":
        return errors.date_out_of_order(detail)
    if message == "rectification_exceeds":
        return errors.from_problem(
            Problem("rectification_exceeds", 409, MESSAGES["rectification_exceeds"], "corrected_base_cents")
        )
    if message == "invoice_not_rectifiable":
        return errors.from_problem(Problem("invoice_not_rectifiable", 409, MESSAGES["not_rectifiable"]))
    if message == "invalid_invoice" and detail in _FIELDS:
        return errors.invalid_invoice((FieldError(detail, MESSAGES[_FIELDS[detail]]),))
    return None


def is_stale_rectification(exc: psycopg.Error) -> bool:
    """¿La base rechazó la rectificativa porque lo vigente ya no es lo que la API leyó (otra rectificativa llegó antes)?"""
    if exc.sqlstate != "P0001":
        return False
    message = exc.diag.message_primary or ""
    detail = (exc.diag.message_detail or "").strip()
    return message == "rectification_exceeds" or (message == "invalid_invoice" and detail in _STALE_FIELDS)


# --- Lectura: perfil, cliente, serie ----------------------------------------------------------------------------------------------


def get_issuer(conn: Connection[DictRow]) -> DictRow | None:
    """Los tres datos del perfil que deciden si se puede emitir y la retención elegida (`numeric`, es decir `Decimal`, nunca `float`)."""
    return conn.execute(
        "SELECT legal_name, tax_id, fiscal_address, irpf_rate FROM public.business_profiles WHERE owner_id = (SELECT auth.uid())"
    ).fetchone()


def ensure_year_series(conn: Connection[DictRow]) -> None:
    conn.execute("SELECT app.ensure_year_series()")


def get_client(conn: Connection[DictRow], client_id: UUID) -> DictRow | None:
    return conn.execute(
        "SELECT id, name, kind::text AS kind, country, scope::text AS scope, tax_id, address, (archived_at IS NOT NULL) AS archived "
        "FROM public.clients WHERE id = %s AND owner_id = (SELECT auth.uid())",
        (client_id,),
    ).fetchone()


_SERIES = (
    "SELECT s.id, s.code, s.kind::text AS kind, (s.archived_at IS NOT NULL) AS archived, "
    "(SELECT max(i.issue_date) FROM public.invoices i WHERE i.owner_id = s.owner_id AND i.series_id = s.id) AS last_issue_date "
    "FROM public.invoice_series s WHERE s.owner_id = (SELECT auth.uid()) AND "
)


def get_series(conn: Connection[DictRow], series_id: UUID) -> DictRow | None:
    """Una serie de la persona, sea del tipo que sea (el dominio rechaza la que no es ordinaria y activa)."""
    return conn.execute(_SERIES + "s.id = %s", (series_id,)).fetchone()


def get_default_series(conn: Connection[DictRow]) -> DictRow | None:
    return conn.execute(_SERIES + "s.is_default AND s.archived_at IS NULL AND s.kind = 'standard'").fetchone()


def ensure_rectifying_series(conn: Connection[DictRow], year: int) -> UUID:
    row = conn.execute("SELECT app.ensure_rectifying_series(%s) AS id", (year,)).fetchone()
    assert row is not None
    return row["id"]


# --- Lectura: facturas ----------------------------------------------------------------------------------------------------------


def get_invoice(conn: Connection[DictRow], invoice_id: UUID) -> DictRow | None:
    return conn.execute(f"{INVOICE_SELECT} WHERE i.id = %s AND {_OWN}", (invoice_id,)).fetchone()


def list_invoices(
    conn: Connection[DictRow],
    year: int,
    scope: str | None,
    paid: bool | None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[DictRow]:
    """Las del año por fecha de expedición, la más reciente primero. `paid` filtra solo las ordinarias: una rectificativa no se cobra, así que ni
    es «cobrada» ni está «pendiente de cobro». `limit` y `offset` (solo el gestor, que pide por páginas) acotan la respuesta; sin ellos, todas."""
    return conn.execute(
        f"{INVOICE_SELECT} WHERE {_OWN} AND i.issue_date >= %(start)s AND i.issue_date < %(end)s "
        "AND (%(scope)s::text IS NULL OR i.client_scope::text = %(scope)s::text) "
        "AND (%(paid)s::boolean IS NULL OR (i.kind = 'standard' AND (i.paid_at IS NOT NULL) = %(paid)s::boolean)) "
        "ORDER BY i.issue_date DESC, i.created_at DESC, i.id DESC LIMIT %(limit)s OFFSET %(offset)s",
        {
            "start": date(year, 1, 1),
            "end": date(year + 1, 1, 1),
            "scope": scope,
            "paid": paid,
            "limit": limit,
            "offset": offset,
        },
    ).fetchall()


def pdf_source(conn: Connection[DictRow], invoice_id: UUID) -> DictRow | None:
    """Todo lo que el PDF dibuja: las copias congeladas del emisor y del cliente de la fila (nunca el perfil de ahora) y, en una rectificativa, la
    factura que rectifica."""
    return conn.execute(
        "SELECT i.id, i.kind::text AS kind, i.series_code, i.number, i.issue_date, i.issuer_name, i.issuer_tax_id, i.issuer_address, i.issuer_iban, "
        "i.client_name, i.client_tax_id, i.client_address, i.concept, i.base_cents, i.vat_rate, i.vat_cents, i.irpf_rate, i.irpf_cents, "
        "i.total_cents, i.legal_note, i.rectification_reason, o.series_code AS original_series_code, o.number AS original_number, "
        "o.issue_date AS original_issue_date "
        "FROM public.invoices i LEFT JOIN public.invoices o ON o.id = i.rectifies_id "
        "WHERE i.id = %s AND i.owner_id = (SELECT auth.uid())",
        (invoice_id,),
    ).fetchone()


def get_file(conn: Connection[DictRow], invoice_id: UUID) -> DictRow | None:
    """El registro del PDF de una factura propia: ruta, huella y tamaño. `None` si aún no tiene."""
    return conn.execute(
        "SELECT storage_path, sha256, size_bytes FROM public.invoice_files WHERE invoice_id = %s AND owner_id = (SELECT private.read_owner())",
        (invoice_id,),
    ).fetchone()


def rectified_by(conn: Connection[DictRow], invoice_ids: list[UUID]) -> dict[UUID, list[tuple[str, int]]]:
    """Las rectificativas de cada factura: (código de serie, número), por orden de emisión."""
    if not invoice_ids:
        return {}
    rows = conn.execute(
        "SELECT rectifies_id, series_code, number FROM public.invoices "
        "WHERE rectifies_id = ANY(%s) AND owner_id = (SELECT private.read_owner()) ORDER BY issue_date, created_at, id",
        (invoice_ids,),
    ).fetchall()
    found: dict[UUID, list[tuple[str, int]]] = {}
    for row in rows:
        found.setdefault(row["rectifies_id"], []).append((row["series_code"], row["number"]))
    return found


def rectification_rows(conn: Connection[DictRow], original_id: UUID) -> list[DictRow]:
    """Los importes de las rectificativas que ya tiene una factura (para calcular lo vigente)."""
    return conn.execute(
        "SELECT base_cents, vat_rate, vat_cents, irpf_rate, irpf_cents, total_cents FROM public.invoices "
        "WHERE rectifies_id = %s AND owner_id = (SELECT auth.uid()) ORDER BY issue_date, created_at, id",
        (original_id,),
    ).fetchall()


def billing(conn: Connection[DictRow], year: int) -> list[DictRow]:
    """Lo facturado a cada cliente en el año: suma de bases con signo (las rectificativas restan en SU fecha de expedición)."""
    return conn.execute(
        "SELECT client_id, sum(base_cents)::bigint AS billed_cents FROM public.invoices "
        "WHERE owner_id = (SELECT auth.uid()) AND issue_date >= %(start)s AND issue_date < %(end)s "
        "GROUP BY client_id ORDER BY client_id",
        {"start": date(year, 1, 1), "end": date(year + 1, 1, 1)},
    ).fetchall()


# --- Escritura (solo funciones app.*) ---------------------------------------------------------------------------------------------


def _whole(rate: Decimal) -> int:
    """Un tipo (21.00, 15.00…) como entero JSON: la base solo admite 0, 4, 7, 10, 15 y 21."""
    whole = int(rate)
    if Decimal(whole) != rate:
        raise ValueError("Los tipos de IVA y de retención son enteros.")
    return whole


def issue(conn: Connection[DictRow], values: InvoiceValues) -> UUID:
    amounts, terms = values.amounts, values.terms
    conditions = {
        "tax_treatment": terms.treatment,
        "vat_rate": _whole(amounts.vat_rate),
        "vat_cents": amounts.vat_cents,
        "irpf_rate": _whole(amounts.irpf_rate),
        "irpf_cents": amounts.irpf_cents,
        "total_cents": amounts.total_cents,
        "legal_note": terms.legal_note,
    }
    row = conn.execute(
        "SELECT app.issue_invoice(%s, %s, %s, %s, %s, %s) AS id",
        (
            UUID(values.client_id),
            UUID(values.series_id),
            values.issue_date,
            values.concept,
            amounts.base_cents,
            Jsonb(conditions),
        ),
    ).fetchone()
    assert row is not None
    return row["id"]


def issue_rectification(conn: Connection[DictRow], values: RectificationValues) -> UUID:
    amounts = values.amounts
    conditions = {"vat_cents": amounts.vat_cents, "irpf_cents": amounts.irpf_cents, "total_cents": amounts.total_cents}
    row = conn.execute(
        "SELECT app.issue_rectifying_invoice(%s, %s, %s, %s, %s) AS id",
        (UUID(values.original_id), values.reason, values.corrected_base_cents, values.issue_date, Jsonb(conditions)),
    ).fetchone()
    assert row is not None
    return row["id"]


def attach_pdf(conn: Connection[DictRow], invoice_id: UUID, path: str, sha256: str, size: int) -> None:
    conn.execute("SELECT app.attach_invoice_pdf(%s, %s, %s, %s)", (invoice_id, path, sha256, size))


def is_pdf_already_attached(exc: psycopg.Error) -> bool:
    """`invoice_pdf_exists`: otra petición registró el PDF antes. Para quien lo pidió es un éxito (el PDF existe)."""
    return exc.sqlstate == "P0001" and (exc.diag.message_primary or "") == "invoice_pdf_exists"


def set_paid(conn: Connection[DictRow], invoice_id: UUID, paid: bool) -> None:
    conn.execute("SELECT app.set_invoice_paid(%s, %s)", (invoice_id, paid))
