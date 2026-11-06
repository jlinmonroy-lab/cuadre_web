"""SQL de documentos (SQL explícito, sin ORM; ADR-0003). Toda escritura pasa por las funciones `app.*` del hito 1.

Las funciones reciben una conexión que ya tiene la identidad de la persona (`user_transaction`). Los errores de la base de datos se
traducen en `translate_db_error`; lo que no se reconoce se propaga y la API lo responde como un 500 sin detalles.
"""

from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError, forbidden
from cuadre.documents import errors
from cuadre.documents.limits import LIST_LIMIT, PROCESSING_TIMEOUT_SECONDS

# `stale`: lectura interrumpida (más de 120 s en `processing`). Se calcula con el reloj de la base de datos, que es el que escribe `updated_at`.
COLUMNS = (
    "id, status::text AS status, source::text AS source, original_filename, mime_type, size_bytes, storage_path, "
    "extraction, review, injection_suspected, error_code, created_at, uploaded_at, extracted_at, updated_at, "
    "(status = 'processing' AND updated_at <= now() - make_interval(secs => %(timeout)s)) AS stale"
)

_PROBLEMS = {
    "document_not_found": errors.document_not_found,
    "document_wrong_state": errors.document_wrong_state,
    "too_many_processing": errors.too_many_processing,
}


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` (hito 1) -> problem+json. `None` si no es uno de ellos."""
    if exc.sqlstate == "42501":
        return forbidden()
    if exc.sqlstate == "P0001":
        factory = _PROBLEMS.get(exc.diag.message_primary or "")
        return factory() if factory is not None else None
    return None


# --- Lectura -----------------------------------------------------------------------------------------------------------------


def get(conn: Connection[DictRow], document_id: UUID) -> DictRow | None:
    """El documento de quien llama (aunque esté descartado), o `None`. `owner_id` se filtra además de la RLS."""
    return conn.execute(
        f"SELECT {COLUMNS} FROM public.documents WHERE id = %(id)s AND owner_id = (SELECT auth.uid())",
        {"id": document_id, "timeout": PROCESSING_TIMEOUT_SECONDS},
    ).fetchone()


def list_visible(conn: Connection[DictRow]) -> list[DictRow]:
    """Los documentos de quien llama que no están `uploading` ni `discarded`, del más reciente al más antiguo."""
    return conn.execute(
        f"SELECT {COLUMNS} FROM public.documents "
        "WHERE owner_id = (SELECT auth.uid()) AND status NOT IN ('uploading', 'discarded') "
        "ORDER BY created_at DESC, id LIMIT %(limit)s",
        {"timeout": PROCESSING_TIMEOUT_SECONDS, "limit": LIST_LIMIT},
    ).fetchall()


# --- Escritura (solo funciones app.*) ------------------------------------------------------------------------------------------


def create_document(
    conn: Connection[DictRow], filename: str, mime_type: str, size_bytes: int, source: str
) -> tuple[UUID, str]:
    row = conn.execute(
        "SELECT document_id, object_path FROM app.create_document(%s, %s, %s, %s::public.upload_source)",
        (filename, mime_type, size_bytes, source),
    ).fetchone()
    assert row is not None
    return row["document_id"], row["object_path"]


def mark_uploaded(conn: Connection[DictRow], document_id: UUID) -> None:
    conn.execute("SELECT app.mark_document_uploaded(%s)", (document_id,))


def record_extraction(
    conn: Connection[DictRow],
    document_id: UUID,
    extraction: dict[str, Any],
    injection_suspected: bool,
    trace_id: str | None,
    cost_eur: Any,
) -> None:
    conn.execute(
        "SELECT app.record_extraction(%s, %s, %s, %s, %s)",
        (document_id, Jsonb(extraction), injection_suspected, trace_id, cost_eur),
    )


def fail_extraction(conn: Connection[DictRow], document_id: UUID, code: str) -> None:
    conn.execute("SELECT app.fail_extraction(%s, %s)", (document_id, code))


def retry(conn: Connection[DictRow], document_id: UUID) -> None:
    conn.execute("SELECT app.retry_document(%s)", (document_id,))


def save_review(conn: Connection[DictRow], document_id: UUID, review: dict[str, Any]) -> None:
    conn.execute("SELECT app.save_document_review(%s, %s)", (document_id, Jsonb(review)))


def discard(conn: Connection[DictRow], document_id: UUID) -> None:
    conn.execute("SELECT app.discard_document(%s)", (document_id,))
