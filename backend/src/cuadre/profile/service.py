"""Los flujos del perfil, el logo y las series (SPEC-W-005 §5.3 y §5.4).

Reglas que importan:

* **Una lectura no escribe** (T5-08): `get_profile` y `list_series` solo leen. La serie del año la crea `update_profile`, en la misma
  transacción que guarda el perfil (D-07).
* **Todo o nada** (§5.1): se valida todo con `cuadre.profile` antes de tocar la base; si algo falla, no se guarda ningún campo y se
  devuelven todos los errores.
* **Storage con el JWT de la persona** (T2-03) y sin retener una conexión mientras se llama a Storage: cada paso abre su transacción corta.
* **Nada personal en los registros** (T5-05): ni NIF, IBAN, nombre, domicilio ni URL firmadas. Los mensajes dicen el campo, no el valor.
"""

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.db import user_transaction
from cuadre.documents.errors import storage_unavailable
from cuadre.documents.storage import StorageError, StorageGateway, StorageNotFound
from cuadre.profile import errors, repository
from cuadre.profile.limits import LOGO_HEAD_BYTES, LOGO_TYPES
from cuadre.profile.logo import declared_problem, extension_for, signature_matches
from cuadre.profile.models import (
    Completeness,
    InvoiceSeries,
    LogoUploadInstructions,
    LogoUploadRequest,
    LogoUploadResponse,
    LogoUrl,
    MissingField,
    Profile,
    ProfileInput,
    Retention,
    SeriesCreate,
    SeriesUpdate,
)
from cuadre.profile.rules import completeness, format_rate, retention, validate_profile
from cuadre.profile.series import (
    DEFAULT_FIRST_NUMBER,
    validate_code,
    validate_description,
    validate_first_number,
    validate_series,
)
from cuadre.profile.types import RawProfile, StoredIdentity

logger = logging.getLogger("cuadre.profile")

LOGO_URL_SECONDS = 60
_EXTENSION_MIME = {ext: mime for mime, ext in LOGO_TYPES.items()}


class ProfileService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], logo_storage: StorageGateway, clock: Clock) -> None:
        self.pool = pool
        self.storage = logo_storage
        self.clock = clock

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

    def _delete_file(self, token: str, path: str) -> None:
        """Borra un objeto con el JWT de la persona. Si falla, queda huérfano (T5-06): no tumba nada."""
        try:
            self.storage.delete(path, token=token)
        except StorageError:
            logger.warning("logo_delete_failed")

    def _profile(self, conn: Connection[DictRow]) -> Profile:
        row = repository.get_profile(conn)
        if row is None:
            raise LookupError("profile_not_found")
        today = today_in_madrid(self.clock)
        done = completeness(StoredIdentity(row["legal_name"], row["tax_id"], row["fiscal_address"]))
        advice = retention(row["activity_start_date"], row["irpf_rate"], today)
        return Profile(
            legal_name=row["legal_name"],
            tax_id=row["tax_id"],
            fiscal_address=row["fiscal_address"],
            activity=row["activity"],
            iae_epigraph=row["iae_epigraph"],
            activity_start_date=row["activity_start_date"],
            vat_regime=row["vat_regime"],
            irpf_rate=None if row["irpf_rate"] is None else format_rate(row["irpf_rate"]),
            home_pct=None if row["home_pct"] is None else format_rate(row["home_pct"]),
            iban=row["iban"],
            has_logo=row["has_logo"],
            updated_at=row["updated_at"],
            completeness=Completeness(
                can_issue=done.can_issue,
                missing_for_invoicing=[MissingField(field=m.field, label=m.label) for m in done.missing_for_invoicing],
            ),
            retention=Retention(
                suggested_rate=advice.suggested_rate,
                reduced_until_year=advice.reduced_until_year,
                warning=advice.warning,
            ),
        )

    # --- Perfil ---------------------------------------------------------------------------------------------------------

    def get_profile(self, user: CurrentUser) -> Profile:
        return self._in_tx(user, self._profile)

    # Lecturas sobre una conexión YA abierta (sin transacción propia): las usa el gestor, que lee y registra en la misma transacción (SPEC-W-010).
    def read_profile(self, conn: Connection[DictRow]) -> Profile:
        return self._profile(conn)

    def read_series(self, conn: Connection[DictRow]) -> list[InvoiceSeries]:
        return [self._series(row) for row in repository.list_series(conn)]

    def update_profile(self, user: CurrentUser, body: ProfileInput) -> Profile:
        result = validate_profile(
            RawProfile(
                legal_name=body.legal_name,
                tax_id=body.tax_id,
                fiscal_address=body.fiscal_address,
                activity=body.activity,
                iae_epigraph=body.iae_epigraph,
                activity_start_date=body.activity_start_date,
                vat_regime=body.vat_regime,
                irpf_rate=body.irpf_rate,
                home_pct=body.home_pct,
                iban=body.iban,
            ),
            today_in_madrid(self.clock),
        )
        if result.values is None:
            raise errors.invalid_profile(result.errors)
        values = result.values

        def work(conn: Connection[DictRow]) -> Profile:
            repository.update_profile(conn, values)
            repository.ensure_year_series(conn)
            return self._profile(conn)

        return self._in_tx(user, work)

    # --- Logo -----------------------------------------------------------------------------------------------------------

    def upload_logo(self, user: CurrentUser, token: str, body: LogoUploadRequest) -> LogoUploadResponse:
        problem = declared_problem(body.mime_type, body.size_bytes)
        if problem == "unsupported_type":
            raise errors.logo_unsupported_type()
        if problem == "too_large":
            raise errors.logo_too_large()
        if problem is not None:
            raise errors.logo_invalid()
        extension = extension_for(body.mime_type)
        assert extension is not None
        upload_id = uuid4()
        try:
            url = self.storage.sign_upload(f"{user.id}/{upload_id}.{extension}", token=token)
        except StorageError:
            raise storage_unavailable() from None
        return LogoUploadResponse(
            upload_id=upload_id, upload=LogoUploadInstructions(url=url, headers={"Content-Type": body.mime_type})
        )

    def complete_logo_upload(self, user: CurrentUser, token: str, upload_id: UUID) -> Profile:
        found: tuple[str, str, int] | None = None  # (ruta, tipo registrado, tamaño registrado)
        for extension in LOGO_TYPES.values():
            path = f"{user.id}/{upload_id}.{extension}"
            try:
                info = self.storage.object_info(path, token=token)
            except StorageError:
                raise storage_unavailable() from None
            if info is not None:
                found = (path, info.content_type, info.size)
                break
        if found is None:
            raise errors.logo_invalid()
        path, registered, size = found
        mime = _EXTENSION_MIME[path.rsplit(".", 1)[1]]
        # El tipo que Storage registró, el tamaño y la firma del archivo tienen que coincidir con la extensión firmada (T5-06).
        if registered != mime or declared_problem(mime, size) is not None:
            self._delete_file(token, path)
            raise errors.logo_invalid()
        try:
            head = self.storage.read_head(path, token=token, length=LOGO_HEAD_BYTES)
        except StorageNotFound:
            raise errors.logo_invalid() from None
        except StorageError:
            raise storage_unavailable() from None
        if not signature_matches(mime, head):
            self._delete_file(token, path)
            raise errors.logo_invalid()

        def work(conn: Connection[DictRow]) -> tuple[str | None, Profile]:
            previous = repository.set_logo(conn, path)
            return previous, self._profile(conn)

        previous, profile = self._in_tx(user, work)
        if previous is not None and previous != path:
            self._delete_file(token, previous)
        return profile

    def get_logo(self, user: CurrentUser, token: str) -> LogoUrl:
        path = self._in_tx(user, repository.logo_path)
        if path is None:
            raise errors.logo_not_found()
        try:
            url = self.storage.sign_read(path, token=token, expires_in=LOGO_URL_SECONDS)
        except StorageNotFound:
            raise errors.logo_not_found() from None
        except StorageError:
            raise storage_unavailable() from None
        return LogoUrl(url=url, expires_in=LOGO_URL_SECONDS)

    def delete_logo(self, user: CurrentUser, token: str) -> None:
        previous = self._in_tx(user, repository.clear_logo)
        if previous is not None:
            self._delete_file(token, previous)

    # --- Series ---------------------------------------------------------------------------------------------------------

    @staticmethod
    def _series(row: Any) -> InvoiceSeries:
        return InvoiceSeries(**{key: row[key] for key in InvoiceSeries.model_fields})

    def list_series(self, user: CurrentUser) -> list[InvoiceSeries]:
        return [self._series(row) for row in self._in_tx(user, repository.list_series)]

    def _read_series(self, conn: Connection[DictRow], series_id: UUID) -> InvoiceSeries:
        row = repository.get_series(conn, series_id)
        if row is None:
            raise errors.series_not_found()
        return self._series(row)

    def create_series(self, user: CurrentUser, body: SeriesCreate) -> InvoiceSeries:
        first = DEFAULT_FIRST_NUMBER if body.first_number is None else body.first_number
        result = validate_series(body.code, body.description, first)
        if result.errors:
            raise errors.invalid_series(result.errors[0].field, result.errors[0].message)
        code, first_number = result.code, result.first_number
        assert code is not None and first_number is not None

        def work(conn: Connection[DictRow]) -> InvoiceSeries:
            series_id = repository.create_series(conn, code, result.description, first_number, body.make_default)
            return self._read_series(conn, series_id)

        return self._in_tx(user, work)

    def update_series(self, user: CurrentUser, series_id: UUID, body: SeriesUpdate) -> InvoiceSeries:
        sent = body.model_fields_set
        changes: dict[str, object] = {}
        if "code" in sent:
            code, message = validate_code(body.code)
            if message is not None:
                raise errors.invalid_series("code", message)
            changes["code"] = code
        if "description" in sent:
            description, message = validate_description(body.description)
            if message is not None:
                raise errors.invalid_series("description", message)
            changes["description"] = description
        if "first_number" in sent:
            number, message = validate_first_number(body.first_number)
            if message is not None:
                raise errors.invalid_series("first_number", message)
            changes["first_number"] = number
        archived = body.archived
        if "archived" in sent and archived is None:
            raise errors.invalid_series("archived", "Indica si la serie se archiva o se reactiva.")

        def work(conn: Connection[DictRow]) -> InvoiceSeries:
            if changes:
                repository.update_series(conn, series_id, changes)
            if archived is not None:
                repository.set_series_archived(conn, series_id, archived)
            return self._read_series(conn, series_id)

        return self._in_tx(user, work)

    def set_default_series(self, user: CurrentUser, series_id: UUID) -> InvoiceSeries:
        def work(conn: Connection[DictRow]) -> InvoiceSeries:
            repository.set_default_series(conn, series_id)
            return self._read_series(conn, series_id)

        return self._in_tx(user, work)
