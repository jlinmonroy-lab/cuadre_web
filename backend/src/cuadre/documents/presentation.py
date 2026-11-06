"""De una fila de `documents` a lo que ve la persona (SPEC-W-002 §5.1 y §5.3).

No se exponen la ruta de Storage, la traza del agente ni su coste. Un `processing` con más de 120 s sin cambios (lectura interrumpida,
AC-11) se PRESENTA como `extraction_failed` con motivo `timeout`, sin escribir nada: la escritura la hace el reintento.
"""

from typing import Any

from psycopg.rows import DictRow

from cuadre.agents import FailureCode
from cuadre.documents.limits import FAILURE_MESSAGES
from cuadre.documents.models import (
    Document,
    DocumentError,
    DocumentState,
    DocumentStatus,
    DocumentSummary,
    Extraction,
    Review,
)


def status_of(row: DictRow) -> DocumentStatus:
    status: DocumentStatus = "extraction_failed" if row["stale"] else row["status"]
    return status


def error_of(row: DictRow) -> DocumentError | None:
    if row["stale"]:
        code = FailureCode.timeout
    elif row["status"] == "extraction_failed" and row["error_code"]:
        code = FailureCode(row["error_code"])
    else:
        return None
    return DocumentError(code=code.value, message=FAILURE_MESSAGES[code])  # type: ignore[arg-type]


def to_state(row: DictRow) -> DocumentState:
    return DocumentState(id=row["id"], status=status_of(row))


def to_document(row: DictRow) -> Document:
    return Document(
        id=row["id"],
        status=status_of(row),
        source=row["source"],
        original_filename=row["original_filename"],
        mime_type=row["mime_type"],
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
        uploaded_at=row["uploaded_at"],
        extracted_at=row["extracted_at"],
        updated_at=row["updated_at"],
        extraction=Extraction.model_validate(row["extraction"]) if row["extraction"] is not None else None,
        review=Review.model_validate(row["review"]) if row["review"] is not None else None,
        injection_suspected=row["injection_suspected"],
        error=error_of(row),
    )


def to_summary(row: DictRow) -> DocumentSummary:
    # La interfaz muestra `review` si existe y `extraction` si no.
    shown: dict[str, Any] = row["review"] if row["review"] is not None else (row["extraction"] or {})
    doubts = (row["extraction"] or {}).get("doubtful_fields", [])
    return DocumentSummary(
        id=row["id"],
        status=status_of(row),
        original_filename=row["original_filename"],
        mime_type=row["mime_type"],
        created_at=row["created_at"],
        doc_type=shown.get("doc_type"),
        supplier_name=shown.get("supplier_name"),
        total_cents=shown.get("total_cents"),
        doubtful_count=len(doubts),
        injection_suspected=row["injection_suspected"],
        error=error_of(row),
    )
