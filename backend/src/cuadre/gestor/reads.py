"""Las lecturas del gestor por autónomo, la cartera, las anotaciones y el registro de actividad (SPEC-W-010 §5.3 y §5.4).

* **Solo lee** (CONF-001 a): lo único que escribe un gestor aquí es una anotación, por `app.add_gestor_note`.
* **Cada lectura, con vínculo y registro en la misma transacción** (`cuadre.gestor.scope`): primero se comprueba el vínculo y se registra; después se lee con
  las MISMAS consultas y presentadores del autónomo (el dueño lo fija `cuadre.read_owner`). Si el registro falla, no se devuelve el dato.
* **Los archivos no pasan por la API** (ADR-0016): el PDF de una factura y el original de un documento salen por URL firmada de corta vida, firmada DESPUÉS
  de confirmar la transacción y con el JWT del propio gestor (la política de Storage ya le deja leer lo de sus autónomos).
* **Sin datos en los registros** (T10-06): ni importes, nombres, NIF, IBAN, conceptos ni URLs firmadas.
"""

import re
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.clients import repository as clients_repository
from cuadre.clients.models import Client
from cuadre.core.auth import CurrentUser
from cuadre.db import user_transaction
from cuadre.documents import errors as documents_errors
from cuadre.documents import presentation as documents_presentation
from cuadre.documents import repository as documents_repository
from cuadre.documents.errors import storage_unavailable
from cuadre.documents.limits import PREVIEW_URL_SECONDS
from cuadre.documents.models import DocumentSummary
from cuadre.documents.storage import StorageError, StorageGateway, StorageNotFound
from cuadre.expenses import cursor as expenses_cursor
from cuadre.expenses import errors as expenses_errors
from cuadre.expenses import presentation as expenses_presentation
from cuadre.expenses import repository as expenses_repository
from cuadre.expenses.models import ExpenseCategory
from cuadre.gestor import errors
from cuadre.gestor.models import (
    ActivityEntry,
    ActivityPage,
    AutonomoSummary,
    ExpenseListPage,
    GestorNote,
    NoteInput,
    PortfolioEntry,
    ProfileView,
    SignedUrl,
)
from cuadre.gestor.scope import begin, read_as_gestor
from cuadre.invoicing import errors as invoicing_errors
from cuadre.invoicing import repository as invoicing_repository
from cuadre.invoicing.models import Invoice
from cuadre.invoicing.service import InvoiceService
from cuadre.profile.service import ProfileService
from cuadre.quarters.models import Modelo130, Modelo303
from cuadre.quarters.service import QuarterService

SIGNED_URL_SECONDS = PREVIEW_URL_SECONDS  # ≈ 60 s, como la vista previa de un documento
EXPENSE_LIST_DEFAULT = 50
EXPENSE_LIST_MAX = 100
NOTES_LIMIT = 200
ACTIVITY_PAGE = 50
FOR_REVIEW = ("review", "extraction_failed")
_CURSOR = re.compile(r"[0-9]{1,18}")

PENDING = (
    "(SELECT count(*) FROM public.documents d WHERE d.owner_id = {owner} AND d.status = 'review')::int AS pending_count"
)


class GestorReadService:
    def __init__(
        self,
        pool: ConnectionPool[Connection[DictRow]],
        invoices: InvoiceService,
        profile: ProfileService,
        quarters: QuarterService,
        documents_storage: StorageGateway,
        invoice_storage: StorageGateway,
    ) -> None:
        self.pool = pool
        self.invoices = invoices
        self.profile = profile
        self.quarters = quarters
        self.documents_storage = documents_storage
        self.invoice_storage = invoice_storage

    def _read[T](self, gestor: CurrentUser, owner: UUID, entity_type: str, work, **kwargs) -> T:  # noqa: ANN001, ANN003
        return read_as_gestor(self.pool, gestor, owner, entity_type, work, **kwargs)

    # --- Cartera y ficha ----------------------------------------------------------------------------------------------------------

    def portfolio(self, gestor: CurrentUser) -> list[PortfolioEntry]:
        """Los autónomos con vínculo ACTIVO con este gestor y sus pendientes. Una entrada `gestor.read` (`portfolio`) por cada autónomo que se enseña."""
        with user_transaction(self.pool, gestor.id, gestor.claims) as conn:
            rows = conn.execute(
                "SELECT g.owner_id AS id, p.display_name AS name, p.email, "
                + PENDING.format(owner="g.owner_id")
                + " FROM public.gestor_access g JOIN public.profiles p ON p.id = g.owner_id "
                "WHERE g.gestor_id = (SELECT auth.uid()) AND g.status = 'active' "
                'ORDER BY pending_count DESC, p.display_name COLLATE "es-x-icu", g.owner_id'
            ).fetchall()
            if rows:
                conn.execute(
                    "SELECT app.log_gestor_read(o, 'portfolio', NULL, NULL) FROM unnest(%s::uuid[]) AS o",
                    ([r["id"] for r in rows],),
                )
        return [PortfolioEntry(**row) for row in rows]

    def autonomo(self, gestor: CurrentUser, owner: UUID) -> AutonomoSummary:
        def work(conn: Connection[DictRow]) -> DictRow | None:
            return conn.execute(
                "SELECT p.id, p.display_name AS name, p.email, "
                + PENDING.format(owner="p.id")
                + " FROM public.profiles p WHERE p.id = %s",
                (owner,),
            ).fetchone()

        row = self._read(gestor, owner, "portfolio", work, entity_id=str(owner))
        if row is None:
            raise errors.not_found()
        return AutonomoSummary(**row)

    # --- Facturas -----------------------------------------------------------------------------------------------------------------

    def invoices_list(
        self,
        gestor: CurrentUser,
        owner: UUID,
        year: int | None,
        scope: str | None,
        paid: bool | None,
        limit: int,
        offset: int,
    ) -> list[Invoice]:
        return self._read(
            gestor,
            owner,
            "invoices",
            lambda conn: self.invoices.read_invoices(conn, year, scope, paid, limit=limit, offset=offset),
            metadata=None if year is None else {"year": year},
        )

    def invoice(self, gestor: CurrentUser, owner: UUID, invoice_id: UUID) -> Invoice:
        return self._read(
            gestor,
            owner,
            "invoice",
            lambda conn: self.invoices.read_invoice(conn, invoice_id),
            entity_id=str(invoice_id),
        )

    def invoice_pdf(self, gestor: CurrentUser, owner: UUID, invoice_id: UUID, token: str) -> SignedUrl:
        def work(conn: Connection[DictRow]) -> str:
            if invoicing_repository.get_invoice(conn, invoice_id) is None:
                raise invoicing_errors.invoice_not_found()
            file = invoicing_repository.get_file(conn, invoice_id)
            if file is None:
                raise invoicing_errors.invoice_pdf_pending()
            return str(file["storage_path"])

        path = self._read(gestor, owner, "invoice_pdf", work, entity_id=str(invoice_id))
        return self._sign(self.invoice_storage, path, token, missing=invoicing_errors.invoice_pdf_corrupt)

    def _sign(self, storage: StorageGateway, path: str, token: str, *, missing) -> SignedUrl:  # noqa: ANN001
        try:
            url = storage.sign_read(path, token=token, expires_in=SIGNED_URL_SECONDS)
        except StorageNotFound:
            raise missing() from None
        except StorageError:
            raise storage_unavailable() from None
        return SignedUrl(url=url, expires_in=SIGNED_URL_SECONDS)

    # --- Gastos y documentos ------------------------------------------------------------------------------------------------------

    def expenses(
        self,
        gestor: CurrentUser,
        owner: UUID,
        *,
        limit: int,
        page: str | None,
        year: int | None,
        month: int | None,
        category: ExpenseCategory | None,
    ) -> ExpenseListPage:
        if month is not None and year is None:
            raise expenses_errors.month_needs_year()
        after = expenses_cursor.decode(page) if page is not None else None

        def work(conn: Connection[DictRow]) -> list[DictRow]:
            return expenses_repository.list_page(
                conn,
                limit=limit + 1,
                after=after,
                year=year,
                month=month,
                category=category.value if category is not None else None,
                include_voided=True,
            )

        rows = self._read(gestor, owner, "expenses", work, metadata=None if year is None else {"year": year})
        shown = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = shown[-1]
            next_cursor = expenses_cursor.encode((last["expense_date"], last["created_at"], last["id"]))
        return ExpenseListPage(items=[expenses_presentation.to_expense(row) for row in shown], next_cursor=next_cursor)

    def documents(self, gestor: CurrentUser, owner: UUID) -> list[DocumentSummary]:
        def work(conn: Connection[DictRow]) -> list[DictRow]:
            return [row for row in documents_repository.list_visible(conn) if row["status"] in FOR_REVIEW]

        rows = self._read(gestor, owner, "documents", work)
        return [documents_presentation.to_summary(row) for row in rows]

    def document_original(self, gestor: CurrentUser, owner: UUID, document_id: UUID, token: str) -> SignedUrl:
        def work(conn: Connection[DictRow]) -> str:
            row = documents_repository.get(conn, document_id)
            if row is None or row["status"] in ("discarded", "uploading"):
                raise documents_errors.document_not_found()
            return str(row["storage_path"])

        path = self._read(gestor, owner, "document_original", work, entity_id=str(document_id))
        return self._sign(self.documents_storage, path, token, missing=documents_errors.upload_missing)

    # --- Perfil y clientes --------------------------------------------------------------------------------------------------------

    def profile_view(self, gestor: CurrentUser, owner: UUID) -> ProfileView:
        def work(conn: Connection[DictRow]) -> ProfileView:
            return ProfileView(profile=self.profile.read_profile(conn), series=self.profile.read_series(conn))

        return self._read(gestor, owner, "profile", work)

    def clients(self, gestor: CurrentUser, owner: UUID) -> list[Client]:
        return self._read(
            gestor,
            owner,
            "clients",
            lambda conn: [Client(**row) for row in clients_repository.list_clients(conn, True)],
        )

    # --- Borradores 303 y 130 -------------------------------------------------------------------------------------------------------

    def modelo_303(self, gestor: CurrentUser, owner: UUID, year: int | None, quarter: int | None) -> Modelo303:
        y, q = self.quarters.resolve_period(
            year, quarter
        )  # un periodo inválido o futuro se rechaza ANTES de abrir nada, como para el autónomo
        return self.quarters.modelo_303(
            gestor, y, q, on_read=lambda conn: begin(conn, owner, "modelo_303", None, {"year": y, "quarter": q})
        )

    def modelo_130(self, gestor: CurrentUser, owner: UUID, year: int | None, quarter: int | None) -> Modelo130:
        y, q = self.quarters.resolve_period(year, quarter)
        return self.quarters.modelo_130(
            gestor, y, q, on_read=lambda conn: begin(conn, owner, "modelo_130", None, {"year": y, "quarter": q})
        )

    # --- Anotaciones ----------------------------------------------------------------------------------------------------------------

    def create_note(self, gestor: CurrentUser, owner: UUID, body: NoteInput) -> GestorNote:
        try:
            with user_transaction(self.pool, gestor.id, gestor.claims) as conn:
                row = conn.execute(
                    "SELECT app.add_gestor_note(%s, %s, %s, %s) AS id",
                    (owner, body.body, body.entity_type, body.entity_id),
                ).fetchone()
                assert row is not None
                note = conn.execute(
                    "SELECT id, body, entity_type, entity_id, created_at, NULL::text AS gestor_email FROM public.gestor_notes WHERE id = %s",
                    (row["id"],),
                ).fetchone()
        except psycopg.errors.InsufficientPrivilege:
            raise errors.not_found() from None
        except psycopg.errors.RaiseException as exc:
            if exc.diag.message_primary == "invalid_note":
                raise errors.invalid_note(exc.diag.message_detail or "body") from None
            raise
        assert note is not None
        return GestorNote(**note)

    def notes_of(self, gestor: CurrentUser, owner: UUID) -> list[GestorNote]:
        def work(conn: Connection[DictRow]) -> list[DictRow]:
            return conn.execute(
                "SELECT id, body, entity_type, entity_id, created_at, NULL::text AS gestor_email FROM public.gestor_notes "
                "WHERE owner_id = %s AND gestor_id = (SELECT auth.uid()) ORDER BY created_at DESC, id LIMIT %s",
                (owner, NOTES_LIMIT),
            ).fetchall()

        return [GestorNote(**row) for row in self._read(gestor, owner, "notes", work)]

    # --- Del autónomo: lo que le han anotado y qué ha leído su gestor -----------------------------------------------------------------

    def my_notes(self, user: CurrentUser) -> list[GestorNote]:
        with user_transaction(self.pool, user.id, user.claims) as conn:
            rows = conn.execute(
                "SELECT n.id, n.body, n.entity_type, n.entity_id, n.created_at, "
                "(SELECT a.gestor_email FROM public.gestor_access a WHERE a.owner_id = n.owner_id AND a.gestor_id = n.gestor_id "
                "ORDER BY a.invited_at DESC LIMIT 1) AS gestor_email "
                "FROM public.gestor_notes n WHERE n.owner_id = (SELECT auth.uid()) ORDER BY n.created_at DESC, n.id LIMIT %s",
                (NOTES_LIMIT,),
            ).fetchall()
        return [GestorNote(**row) for row in rows]

    def my_activity(self, user: CurrentUser, cursor: str | None) -> ActivityPage:
        if cursor is not None and _CURSOR.fullmatch(cursor) is None:
            raise errors.invalid_cursor()
        after = int(cursor) if cursor is not None else None
        with user_transaction(self.pool, user.id, user.claims) as conn:
            rows = conn.execute(
                "SELECT l.id, l.occurred_at, l.action, l.actor_role::text AS actor_role, "
                "(SELECT a.gestor_email FROM public.gestor_access a WHERE a.owner_id = l.owner_id AND a.gestor_id = l.actor_id "
                "ORDER BY a.invited_at DESC LIMIT 1) AS actor_email, l.entity_type, l.entity_id, "
                "(l.metadata ->> 'year')::int AS year, (l.metadata ->> 'quarter')::int AS quarter "
                "FROM public.activity_log l WHERE l.owner_id = (SELECT auth.uid()) AND l.category = 'access' "
                "AND (%(after)s::bigint IS NULL OR l.id < %(after)s::bigint) ORDER BY l.id DESC LIMIT %(limit)s",
                {"after": after, "limit": ACTIVITY_PAGE + 1},
            ).fetchall()
        shown = rows[:ACTIVITY_PAGE]
        return ActivityPage(
            items=[ActivityEntry(**row) for row in shown],
            next_cursor=str(shown[-1]["id"]) if len(rows) > ACTIVITY_PAGE else None,
        )
