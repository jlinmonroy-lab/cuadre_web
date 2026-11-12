"""Los flujos de facturas (SPEC-W-007 §5.3 y §5.4).

* **Una lectura no escribe** (T7-07): `preview`, `list_invoices`, `get_invoice` y `billing` solo leen. Emitir y rectificar crean la serie del año
  (`ensure_year_series`, `ensure_rectifying_series`) dentro de la MISMA transacción que la factura: si algo falla, no queda ni la serie.
* **Todo o nada** (§5.1): se valida todo con `cuadre.invoicing` ANTES de llamar a la función de la base; si algo falla, no se emite nada y se devuelven
  todos los errores de campo a la vez. Las condiciones (ámbito, IVA, retención, mención) las calcula el dominio: nunca vienen de quien llama.
* **La base repite lo barato** (B.3): `app.issue_invoice` comprueba que las condiciones son coherentes y, en una rectificativa, RECALCULA lo vigente
  bajo el cerrojo. La API lee antes de bloquear (el rol de la API no puede hacer `FOR UPDATE` sobre `invoices`); si otra rectificativa llegó entre
  medias, la base lo dice y aquí se relee **una vez** y, si vuelve a pasar, `invoice_changed` (409).
* **Sin conexión retenida esperando a Storage** (ADR-0016): el PDF se dibuja, se sube y se registra DESPUÉS de cerrar la transacción de la factura, cada
  paso con su transacción corta. Al emitir o rectificar, un fallo del PDF no tumba la factura (ya está emitida): queda `pending` y `create_pdf` la
  completa. Al pedirlo con `create_pdf`, un fallo sí es un error. El PDF guardado manda por su huella: `get_pdf` la comprueba.
* **Nada de terceros en los registros** (T7-06): ni nombre, NIF, domicilio, IBAN ni concepto. Los mensajes dicen el campo, no el valor.
"""

import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.db import user_transaction
from cuadre.documents.errors import storage_unavailable
from cuadre.documents.storage import StorageDenied, StorageError, StorageNotFound
from cuadre.invoicing import errors, repository
from cuadre.invoicing.models import (
    ClientBilling,
    Invoice,
    InvoiceClient,
    InvoiceInput,
    InvoiceIssuer,
    InvoicePreview,
    InvoiceRef,
    RectificationInput,
    Standing,
)
from cuadre.invoicing.numbering import display_number
from cuadre.invoicing.pdf import render_invoice_pdf
from cuadre.invoicing.rules import issue_year, parse_uuid, validate_invoice, validate_rectification
from cuadre.invoicing.storage import PDF_CONTENT_TYPE, PDF_MAX_BYTES, LogoReader, PdfStorage, sha256_hex
from cuadre.invoicing.storage_path import invoice_pdf_path
from cuadre.invoicing.types import (
    ClientCopy,
    InvoiceValues,
    OriginalInvoice,
    PdfInvoice,
    RawInvoice,
    RawRectification,
    SeriesInfo,
)
from cuadre.profile import repository as profile_repository
from cuadre.profile.limits import LOGO_MAX_BYTES
from cuadre.profile.rules import completeness
from cuadre.profile.types import StoredIdentity
from cuadre.tax import Amounts, invoice_terms

logger = logging.getLogger("cuadre.invoicing")

RETRIES = 2  # lecturas de una rectificativa: la primera y una más si otra rectificativa se coló


def _rate(value: Decimal) -> str:
    """`Decimal('21')` es `"21.00"`: siempre dos decimales, que es como viajan."""
    return format(value.quantize(Decimal("0.01")), "f")


class PdfObjectMismatch(Exception):
    """Ya había un objeto en la ruta del PDF y su contenido no es el que se acaba de dibujar (alguien subió otra cosa a esa ruta)."""


def _amounts(row: DictRow) -> Amounts:
    return Amounts(
        row["base_cents"],
        Decimal(row["vat_rate"]),
        row["vat_cents"],
        Decimal(row["irpf_rate"]),
        row["irpf_cents"],
        row["total_cents"],
    )


class InvoiceService:
    def __init__(
        self,
        pool: ConnectionPool[Connection[DictRow]],
        clock: Clock,
        pdf_storage: PdfStorage,
        logo_storage: LogoReader,
    ) -> None:
        self.pool = pool
        self.clock = clock
        self.pdf_storage = pdf_storage
        self.logo_storage = logo_storage

    # --- Utilidades -----------------------------------------------------------------------------------------------------

    def _in_tx[T](self, user: CurrentUser, work: Callable[[Connection[DictRow]], T]) -> T:
        """Una transacción corta con la identidad de la persona. Los errores de las funciones `app.*` salen como problem+json."""
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                return work(conn)
        except psycopg.Error as exc:
            problem = repository.translate_db_error(exc)
            if problem is None:
                raise
            raise problem from None

    def _today(self) -> date:
        return today_in_madrid(self.clock)

    @staticmethod
    def _issuer(conn: Connection[DictRow]) -> Decimal | None:
        """Comprueba que el perfil permite emitir (US-007) y devuelve la retención elegida, o `None`."""
        row = repository.get_issuer(conn)
        stored = StoredIdentity(*(None if row is None else row[k] for k in ("legal_name", "tax_id", "fiscal_address")))
        done = completeness(stored)
        if not done.can_issue:
            raise errors.profile_incomplete([(m.field, m.label) for m in done.missing_for_invoicing])
        assert row is not None
        return row["irpf_rate"]

    @staticmethod
    def _client_copy(conn: Connection[DictRow], raw: object) -> ClientCopy | None:
        client_id = parse_uuid(raw)
        row = None if client_id is None else repository.get_client(conn, UUID(client_id))
        if row is None:
            return None
        return ClientCopy(
            str(row["id"]),
            row["name"],
            row["kind"],
            row["country"],
            row["scope"],
            row["tax_id"],
            row["address"],
            row["archived"],
        )

    @staticmethod
    def _series_info(row: DictRow | None) -> SeriesInfo | None:
        if row is None:
            return None
        return SeriesInfo(str(row["id"]), row["code"], row["kind"], row["archived"], row["last_issue_date"])

    @classmethod
    def _chosen_series(cls, conn: Connection[DictRow], raw: object) -> SeriesInfo | None:
        """La serie elegida o, si no se eligió ninguna (vacío), la predeterminada. Un texto que no es un uuid no es «vacío»: es una serie que no existe."""
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return cls._series_info(repository.get_default_series(conn))
        series_id = parse_uuid(raw)
        return None if series_id is None else cls._series_info(repository.get_series(conn, UUID(series_id)))

    def _validated(
        self, conn: Connection[DictRow], body: InvoiceInput, irpf: Decimal | None
    ) -> tuple[InvoiceValues, ClientCopy]:
        client = self._client_copy(conn, body.client_id)
        result = validate_invoice(
            RawInvoice(body.client_id, body.series_id, body.issue_date, body.concept, body.base_cents, body.vat_rate),
            client=client,
            series=self._chosen_series(conn, body.series_id),
            irpf_rate=irpf,
            today=self._today(),
        )
        if result.problem is not None:
            raise errors.from_problem(result.problem)
        if result.values is None:
            raise errors.invalid_invoice(result.errors)
        assert client is not None
        return result.values, client

    # --- Lecturas -------------------------------------------------------------------------------------------------------

    def _invoices(self, conn: Connection[DictRow], rows: list[DictRow]) -> list[Invoice]:
        by_original = repository.rectified_by(conn, [r["id"] for r in rows])
        return [
            Invoice(
                id=row["id"],
                series_code=row["series_code"],
                number=row["number"],
                display_number=display_number(row["series_code"], row["number"]),
                kind=row["kind"],
                issue_date=row["issue_date"],
                issuer=InvoiceIssuer(
                    name=row["issuer_name"],
                    tax_id=row["issuer_tax_id"],
                    address=row["issuer_address"],
                    iban=row["issuer_iban"],
                ),
                client=InvoiceClient(
                    id=row["client_id"],
                    name=row["client_name"],
                    kind=row["client_kind"],
                    country=row["client_country"],
                    scope=row["client_scope"],
                    tax_id=row["client_tax_id"],
                    address=row["client_address"],
                ),
                concept=row["concept"],
                tax_treatment=row["tax_treatment"],
                base_cents=row["base_cents"],
                vat_rate=_rate(row["vat_rate"]),
                vat_cents=row["vat_cents"],
                irpf_rate=_rate(row["irpf_rate"]),
                irpf_cents=row["irpf_cents"],
                total_cents=row["total_cents"],
                legal_note=row["legal_note"],
                rectifies=None
                if row["rectifies_id"] is None
                else InvoiceRef(
                    id=row["rectifies_id"],
                    display_number=display_number(row["original_series_code"], row["original_number"]),
                    issue_date=row["original_issue_date"],
                ),
                rectification_reason=row["rectification_reason"],
                rectified_by=[display_number(code, number) for code, number in by_original.get(row["id"], [])],
                standing=None
                if row["standing_base"] is None
                else Standing(
                    base_cents=int(row["standing_base"]),
                    vat_cents=int(row["standing_vat"]),
                    irpf_cents=int(row["standing_irpf"]),
                ),
                paid_at=row["paid_at"],
                pdf_status="ready" if row["has_pdf"] else "pending",
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _invoice(self, conn: Connection[DictRow], invoice_id: UUID) -> Invoice:
        row = repository.get_invoice(conn, invoice_id)
        if row is None:
            raise errors.invoice_not_found()
        return self._invoices(conn, [row])[0]

    def get_invoice(self, user: CurrentUser, invoice_id: UUID) -> Invoice:
        return self._in_tx(user, lambda conn: self._invoice(conn, invoice_id))

    # Lecturas sobre una conexión YA abierta (sin transacción propia): las usa el gestor, que lee y registra en la misma transacción (SPEC-W-010).
    def read_invoice(self, conn: Connection[DictRow], invoice_id: UUID) -> Invoice:
        return self._invoice(conn, invoice_id)

    def read_invoices(
        self,
        conn: Connection[DictRow],
        year: int | None,
        scope: str | None,
        paid: bool | None,
        *,
        limit: int,
        offset: int,
    ) -> list[Invoice]:
        chosen = year if year is not None else self._today().year
        return self._invoices(conn, repository.list_invoices(conn, chosen, scope, paid, limit=limit, offset=offset))

    def list_invoices(self, user: CurrentUser, year: int | None, scope: str | None, paid: bool | None) -> list[Invoice]:
        chosen = year if year is not None else self._today().year
        return self._in_tx(user, lambda conn: self._invoices(conn, repository.list_invoices(conn, chosen, scope, paid)))

    def billing(self, user: CurrentUser, year: int | None) -> list[ClientBilling]:
        chosen = year if year is not None else self._today().year
        rows = self._in_tx(user, lambda conn: repository.billing(conn, chosen))
        return [ClientBilling(client_id=row["client_id"], billed_cents=row["billed_cents"]) for row in rows]

    def preview(self, user: CurrentUser, body: InvoiceInput) -> InvoicePreview:
        """Lo que se emitiría, con los mismos errores que emitir y sin escribir nada (T7-07): ni número ni serie del año."""

        def work(conn: Connection[DictRow]) -> InvoicePreview:
            irpf = self._issuer(conn)
            values, client = self._validated(conn, body, irpf)
            amounts = values.amounts
            return InvoicePreview(
                scope=client.scope,
                kind=client.kind,
                tax_treatment=values.terms.treatment,
                base_cents=amounts.base_cents,
                vat_rate=_rate(amounts.vat_rate),
                vat_cents=amounts.vat_cents,
                irpf_rate=_rate(amounts.irpf_rate),
                irpf_cents=amounts.irpf_cents,
                total_cents=amounts.total_cents,
                legal_note=values.terms.legal_note,
                vat_editable=values.terms.vat_editable,
            )

        return self._in_tx(user, work)

    # --- Escrituras -----------------------------------------------------------------------------------------------------

    def issue_invoice(self, user: CurrentUser, token: str, body: InvoiceInput) -> Invoice:
        def work(conn: Connection[DictRow]) -> Invoice:
            irpf = self._issuer(conn)
            repository.ensure_year_series(conn)
            values, _ = self._validated(conn, body, irpf)
            return self._invoice(conn, repository.issue(conn, values))

        return self._with_pdf(user, token, self._in_tx(user, work))

    def set_payment(self, user: CurrentUser, invoice_id: UUID, paid: bool) -> Invoice:
        def work(conn: Connection[DictRow]) -> Invoice:
            repository.set_paid(conn, invoice_id, paid)
            return self._invoice(conn, invoice_id)

        return self._in_tx(user, work)

    def _rectify_once(self, conn: Connection[DictRow], original_id: UUID, body: RectificationInput) -> Invoice:
        row = repository.get_invoice(conn, original_id)
        if row is None:
            raise errors.invoice_not_found()
        self._issuer(conn)
        today = self._today()
        original = OriginalInvoice(
            str(row["id"]),
            display_number(row["series_code"], row["number"]),
            row["kind"],
            row["issue_date"],
            invoice_terms(row["client_scope"], row["client_kind"]),
            _amounts(row),
        )
        previous = [_amounts(r) for r in repository.rectification_rows(conn, original_id)]
        # La serie rectificativa es la del AÑO de la fecha de expedición; si la fecha no se entiende, la del año de hoy (solo sirve para validar:
        # el error de la fecha sale igualmente).
        year = issue_year(body.issue_date) or today.year
        series = self._series_info(repository.get_series(conn, repository.ensure_rectifying_series(conn, year)))
        assert series is not None
        result = validate_rectification(
            RawRectification(body.reason, body.corrected_base_cents, body.issue_date),
            original=original,
            rectifications=previous,
            series=series,
            today=today,
        )
        if result.problem is not None:
            raise errors.from_problem(result.problem)
        if result.values is None:
            raise errors.invalid_invoice(result.errors)
        return self._invoice(conn, repository.issue_rectification(conn, result.values))

    def issue_rectification(
        self, user: CurrentUser, token: str, original_id: UUID, body: RectificationInput
    ) -> Invoice:
        return self._with_pdf(user, token, self._rectify(user, original_id, body))

    def _rectify(self, user: CurrentUser, original_id: UUID, body: RectificationInput) -> Invoice:
        for attempt in range(RETRIES):
            try:
                with user_transaction(self.pool, user.id, user.claims) as conn:
                    return self._rectify_once(conn, original_id, body)
            except psycopg.Error as exc:
                if repository.is_stale_rectification(exc):
                    if attempt + 1 < RETRIES:
                        continue
                    raise errors.invoice_changed() from None
                problem = repository.translate_db_error(exc)
                if problem is None:
                    raise
                raise problem from None
        raise errors.invoice_changed()  # pragma: no cover - el bucle siempre devuelve o lanza

    # --- El PDF (paso 3 de §5.4): fuera de la transacción de la factura --------------------------------------------------------

    @staticmethod
    def _pdf_data(row: DictRow) -> PdfInvoice:
        rectifying = row["kind"] == "rectifying"
        return PdfInvoice(
            display_number=display_number(row["series_code"], row["number"]),
            kind=row["kind"],
            issue_date=row["issue_date"],
            issuer_name=row["issuer_name"],
            issuer_tax_id=row["issuer_tax_id"],
            issuer_address=row["issuer_address"],
            issuer_iban=row["issuer_iban"],
            client_name=row["client_name"],
            client_tax_id=row["client_tax_id"],
            client_address=row["client_address"],
            concept=row["concept"],
            base_cents=row["base_cents"],
            vat_rate=Decimal(row["vat_rate"]),
            vat_cents=row["vat_cents"],
            irpf_rate=Decimal(row["irpf_rate"]),
            irpf_cents=row["irpf_cents"],
            total_cents=row["total_cents"],
            legal_note=row["legal_note"],
            rectifies_number=display_number(row["original_series_code"], row["original_number"])
            if rectifying
            else None,
            rectifies_date=row["original_issue_date"] if rectifying else None,
            rectification_reason=row["rectification_reason"] if rectifying else None,
        )

    def _read_logo(self, token: str, path: str | None) -> bytes | None:
        """El logo del perfil, o `None`. Cualquier fallo (sin logo, Storage caído, objeto raro) es «sin logo»: la factura sale igualmente."""
        if path is None:
            return None
        try:
            data = self.logo_storage.download(path, token=token, max_bytes=LOGO_MAX_BYTES)
        except StorageError:
            return None
        return data if len(data) <= LOGO_MAX_BYTES else None

    def _store_pdf(self, user: CurrentUser, token: str, invoice_id: UUID) -> None:
        """Dibuja, sube y registra el PDF de una factura propia que aún no lo tiene. Lanza si algo falla; idempotente: con el PDF ya registrado no hace
        nada, con el objeto ya subido (409) lo da por bueno si es el mismo contenido y si otra petición lo registró antes, también."""

        def read(conn: Connection[DictRow]) -> tuple[DictRow | None, DictRow | None, str | None]:
            return (
                repository.pdf_source(conn, invoice_id),
                repository.get_file(conn, invoice_id),
                profile_repository.logo_path(conn),
            )

        source, file, logo_path = self._in_tx(user, read)
        if source is None:
            raise errors.invoice_not_found()
        if file is not None:
            return
        data = render_invoice_pdf(self._pdf_data(source), self._read_logo(token, logo_path))
        if len(data) > PDF_MAX_BYTES:
            raise ValueError("El PDF supera el límite del bucket.")
        sha = sha256_hex(data)
        path = invoice_pdf_path(str(user.id), str(invoice_id), sha)
        uploaded = self.pdf_storage.upload(path, data, PDF_CONTENT_TYPE, token=token)
        if (
            uploaded == "exists"
            and sha256_hex(self.pdf_storage.download(path, token=token, max_bytes=PDF_MAX_BYTES)) != sha
        ):
            raise PdfObjectMismatch
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                repository.attach_pdf(conn, invoice_id, path, sha, len(data))
        except psycopg.Error as exc:
            if not repository.is_pdf_already_attached(exc):
                raise

    def _with_pdf(self, user: CurrentUser, token: str, invoice: Invoice) -> Invoice:
        """Emitir o rectificar ya ha ocurrido: el PDF es un paso aparte que, si falla, deja la factura `pending` (se completa con `create_pdf`)."""
        try:
            self._store_pdf(user, token, invoice.id)
        except Exception as exc:  # noqa: BLE001 - la factura ya está emitida; nunca se escribe qué contenía, solo qué tipo de fallo fue
            logger.warning("invoice_pdf_failed", extra={"reason": type(exc).__name__})
            return invoice
        return invoice.model_copy(update={"pdf_status": "ready"})

    def create_pdf(self, user: CurrentUser, token: str, invoice_id: UUID) -> Invoice:
        """`POST /pdf`: completa el PDF de una factura que no lo tiene. Aquí un fallo SÍ es un error, porque la persona lo pidió."""
        try:
            self._store_pdf(user, token, invoice_id)
        except (StorageError, OSError):
            raise storage_unavailable() from None
        except PdfObjectMismatch:
            raise errors.invoice_pdf_corrupt() from None
        return self._in_tx(user, lambda conn: self._invoice(conn, invoice_id))

    def get_pdf(self, user: CurrentUser, token: str, invoice_id: UUID) -> tuple[bytes, str]:
        """`GET /pdf`: el PDF guardado, comprobando tamaño y huella. Devuelve los bytes y el nombre del archivo (el número de la factura)."""

        def read(conn: Connection[DictRow]) -> tuple[DictRow | None, DictRow | None]:
            return repository.get_invoice(conn, invoice_id), repository.get_file(conn, invoice_id)

        row, file = self._in_tx(user, read)
        if row is None:
            raise errors.invoice_not_found()
        if file is None:
            raise errors.invoice_pdf_pending()
        try:
            data = self.pdf_storage.download(file["storage_path"], token=token, max_bytes=PDF_MAX_BYTES)
        except StorageNotFound:
            raise errors.invoice_pdf_corrupt() from None
        except (StorageDenied, StorageError, OSError):
            raise storage_unavailable() from None
        if len(data) != file["size_bytes"] or sha256_hex(data) != file["sha256"]:
            raise errors.invoice_pdf_corrupt()
        return data, f"{display_number(row['series_code'], row['number'])}.pdf"
