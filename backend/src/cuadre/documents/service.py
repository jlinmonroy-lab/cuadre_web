"""Los flujos de documentos (SPEC-W-002 §5.1): reservar y firmar, completar, reintentar, descartar, corregir y previsualizar.

Reglas que se repiten y que importan:

* **Nunca se retiene una conexión de la base de datos mientras se llama a Storage o al agente.** Cada paso con la base abre su
  transacción corta (`_in_tx`) y la cierra. La lectura espera al agente hasta 45 s (D-02) sin ocupar el pool.
* **El orden es la seguridad.** `complete` comprueba la existencia, el tamaño, el tipo registrado y la firma del archivo ANTES de
  pasar a `processing` y antes de llamar al agente (T2-08); la lectura es idempotente por documento (T2-09).
* **Storage siempre con el JWT de la persona** (T2-03); nunca la service key.
* Nada de lo que contiene un documento (nombre de archivo, URL firmada, JWT, datos leídos) llega a un registro (NFR-11).
"""

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool
from pydantic import ValidationError

from cuadre.agents import AgentsClient, AgentsError, FailureCode, normalize_extraction
from cuadre.agents.text import InvalidText, clean_text
from cuadre.core.auth import CurrentUser
from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction
from cuadre.documents import errors, presentation, repository, signature
from cuadre.documents.limits import (
    MAX_UPLOAD_BYTES,
    MIME_EXTENSIONS,
    PREVIEW_URL_SECONDS,
    READ_URL_SECONDS,
    SIGNATURE_BYTES,
    UNPREVIEWABLE_MIME_TYPES,
)
from cuadre.documents.models import (
    Document,
    DocumentState,
    DocumentSummary,
    PreviewResponse,
    Review,
    UploadInstructions,
    UploadRequest,
    UploadResponse,
)
from cuadre.documents.storage import StorageError, StorageGateway, StorageNotFound
from cuadre_contracts import ExtractRequest

logger = logging.getLogger("cuadre.documents")

# Estados en los que la lectura ya empezó o terminó: `complete` responde el estado actual sin lanzar otra (T2-09).
READING_STATES = frozenset({"processing", "review", "extraction_failed"})


class DocumentService:
    def __init__(
        self, pool: ConnectionPool[Connection[DictRow]], storage: StorageGateway, agents: AgentsClient
    ) -> None:
        self.pool = pool
        self.storage = storage
        self.agents = agents

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

    def _row(self, user: CurrentUser, document_id: UUID) -> DictRow | None:
        return self._in_tx(user, lambda conn: repository.get(conn, document_id))

    def _visible_row(self, user: CurrentUser, document_id: UUID) -> DictRow:
        """El documento, o 404. Para la persona un documento descartado ya no existe."""
        row = self._row(user, document_id)
        if row is None or row["status"] == "discarded":
            raise errors.document_not_found()
        return row

    def _state(self, user: CurrentUser, document_id: UUID) -> DocumentState:
        row = self._row(user, document_id)
        if row is None:
            raise errors.document_not_found()
        return presentation.to_state(row)

    def _delete_file(self, token: str, path: str) -> None:
        """Borra el archivo con el JWT de la persona. Si falla, el huérfano queda para mantenimiento (§4): no tumba nada."""
        try:
            self.storage.delete(path, token=token)
        except StorageError:
            logger.warning("storage_delete_failed")

    def _discard_quietly(self, user: CurrentUser, document_id: UUID) -> None:
        try:
            self._in_tx(user, lambda conn: repository.discard(conn, document_id))
        except (ProblemError, psycopg.Error):
            logger.warning("document_discard_failed", extra={"document_id": str(document_id)})

    # --- Lista y detalle ------------------------------------------------------------------------------------------------

    def list_documents(self, user: CurrentUser) -> list[DocumentSummary]:
        rows = self._in_tx(user, repository.list_visible)
        return [presentation.to_summary(row) for row in rows]

    def get_document(self, user: CurrentUser, document_id: UUID) -> Document:
        return presentation.to_document(self._visible_row(user, document_id))

    def preview(self, user: CurrentUser, token: str, document_id: UUID) -> PreviewResponse:
        row = self._visible_row(user, document_id)
        if row["status"] == "uploading":  # todavía no hay archivo que enseñar
            raise errors.document_wrong_state()
        try:
            url = self.storage.sign_read(row["storage_path"], token=token, expires_in=PREVIEW_URL_SECONDS)
        except StorageNotFound:
            raise errors.upload_missing() from None
        except StorageError:
            raise errors.storage_unavailable() from None
        return PreviewResponse(
            url=url, expires_in=PREVIEW_URL_SECONDS, previewable=row["mime_type"] not in UNPREVIEWABLE_MIME_TYPES
        )

    # --- Reservar y firmar ----------------------------------------------------------------------------------------------

    def create_upload(self, user: CurrentUser, token: str, body: UploadRequest) -> UploadResponse:
        if body.mime_type not in MIME_EXTENSIONS:
            raise errors.unsupported_file_type()
        if body.size_bytes > MAX_UPLOAD_BYTES:
            raise errors.file_too_large()
        try:
            filename = clean_text(body.filename, 255)
        except InvalidText:
            filename = None
        if filename is None:
            raise errors.invalid_filename()

        # Primero la fila (y su commit): la política de INSERT de Storage la mira al firmar y la lee desde otra conexión.
        document_id, path = self._in_tx(
            user, lambda conn: repository.create_document(conn, filename, body.mime_type, body.size_bytes, body.source)
        )
        try:
            url = self.storage.sign_upload(path, token=token)
        except StorageError:
            self._discard_quietly(user, document_id)
            raise errors.storage_unavailable() from None
        return UploadResponse(
            id=document_id,
            status="uploading",
            upload=UploadInstructions(url=url, method="PUT", headers={"Content-Type": body.mime_type}),
            max_bytes=MAX_UPLOAD_BYTES,
        )

    # --- Completar la subida y leer -------------------------------------------------------------------------------------

    def complete(self, user: CurrentUser, token: str, document_id: UUID, request_id: str) -> DocumentState:
        row = self._row(user, document_id)
        if row is None:
            raise errors.document_not_found()
        if row["status"] in READING_STATES:
            return presentation.to_state(row)  # idempotente: no se lanza otra lectura
        if row["status"] != "uploading":
            raise errors.document_wrong_state()

        self._verify_upload(user, token, row)

        try:
            self._in_tx(user, lambda conn: repository.mark_uploaded(conn, document_id))
        except ProblemError as problem:
            # Otra petición lo completó un instante antes: su lectura es la que vale, y a esta se le responde cómo va.
            if problem.code == "document_wrong_state":
                return self._state(user, document_id)
            raise
        return self._read(user, token, row, request_id)

    def retry(self, user: CurrentUser, token: str, document_id: UUID, request_id: str) -> DocumentState:
        row = self._row(user, document_id)
        if row is None:
            raise errors.document_not_found()
        # 409 si no toca reintentar; 429 si no caben más lecturas.
        self._in_tx(user, lambda conn: repository.retry(conn, document_id))
        return self._read(user, token, row, request_id)

    def _verify_upload(self, user: CurrentUser, token: str, row: DictRow) -> None:
        """Existe, pesa lo declarado, Storage lo registró con el tipo declarado y su firma es la de ese tipo (T2-08)."""
        path: str = row["storage_path"]
        try:
            info = self.storage.object_info(path, token=token)
            if info is None:
                raise errors.upload_missing()
            if info.size != row["size_bytes"]:
                self._reject(user, token, row, "size")
                raise errors.upload_size_mismatch()
            if info.content_type.split(";")[0].strip().lower() != row["mime_type"]:
                self._reject(user, token, row, "registered_type")
                raise errors.file_type_mismatch()
            head = self.storage.read_head(path, token=token, length=SIGNATURE_BYTES)
        except StorageNotFound:
            raise errors.upload_missing() from None
        except StorageError:
            raise errors.storage_unavailable() from None
        if not signature.matches(row["mime_type"], head):
            self._reject(user, token, row, "signature")
            raise errors.file_type_mismatch()

    def _reject(self, user: CurrentUser, token: str, row: DictRow, reason: str) -> None:
        """El archivo no es lo que se declaró y una URL de subida admite una sola subida: no hay arreglo, se descarta y se borra."""
        logger.warning("document_upload_rejected", extra={"document_id": str(row["id"]), "reason": reason})
        self._discard_quietly(user, row["id"])
        self._delete_file(token, row["storage_path"])

    def _read(self, user: CurrentUser, token: str, row: DictRow, request_id: str) -> DocumentState:
        """El documento ya está en `processing`: pide la lectura al agente (hasta 45 s, sin conexión retenida) y guarda el resultado."""
        document_id: UUID = row["id"]
        reading = None
        failure = FailureCode.internal
        try:
            url = self.storage.sign_read(row["storage_path"], token=token, expires_in=READ_URL_SECONDS)
            request = ExtractRequest(document_id=document_id, document_url=url, mime_type=row["mime_type"])
            reading = normalize_extraction(self.agents.extract_invoice(request, request_id=request_id))
        except AgentsError as exc:
            failure = exc.code
        except (StorageError, ValidationError):
            failure = FailureCode.internal  # no se pudo ni preparar la lectura: no es culpa del agente ni del documento
        except Exception:
            self._fail_quietly(user, document_id, FailureCode.internal)  # que el documento no se quede en `processing`
            raise

        try:
            if reading is not None:
                extraction = reading
                self._in_tx(
                    user,
                    lambda conn: repository.record_extraction(
                        conn,
                        document_id,
                        extraction.extraction,
                        extraction.injection_suspected,
                        extraction.trace_id,
                        extraction.cost_eur,
                    ),
                )
            else:
                self._in_tx(user, lambda conn: repository.fail_extraction(conn, document_id, failure.value))
        except ProblemError as problem:
            if problem.code not in ("document_wrong_state", "document_not_found"):
                raise
            # Se descartó mientras se leía: no hay nada que guardar; se responde cómo quedó.
        except Exception:
            self._fail_quietly(user, document_id, FailureCode.internal)
            raise
        return self._state(user, document_id)

    def _fail_quietly(self, user: CurrentUser, document_id: UUID, code: FailureCode) -> None:
        try:
            self._in_tx(user, lambda conn: repository.fail_extraction(conn, document_id, code.value))
        except (ProblemError, psycopg.Error):
            logger.warning("document_fail_not_recorded", extra={"document_id": str(document_id)})

    # --- Descartar y corregir -------------------------------------------------------------------------------------------

    def discard(self, user: CurrentUser, token: str, document_id: UUID) -> None:
        row = self._row(user, document_id)
        if row is None:
            raise errors.document_not_found()
        self._in_tx(
            user, lambda conn: repository.discard(conn, document_id)
        )  # 409 si ya estaba descartado o registrado
        self._delete_file(token, row["storage_path"])

    def save_review(self, user: CurrentUser, document_id: UUID, review: Review) -> Document:
        payload: dict[str, Any] = review.model_dump(mode="json")
        self._in_tx(user, lambda conn: repository.save_review(conn, document_id, payload))
        return self.get_document(user, document_id)
