"""Ruta del PDF en el bucket privado `invoices` (SPEC-W-007 §5.2, D-03 y D-10, B.1-C). Python puro.

`{owner_id}/{invoice_id}-{sha256[:16]}.pdf`: el prefijo de la huella hace **idempotente** la subida (el mismo contenido da siempre la misma ruta,
y un 409 de Storage significa «ya está»). El hito 2 compara `PDF_PATH` con la política del bucket.
"""

from cuadre.invoicing.limits import PDF_HASH_PREFIX, PDF_PATH, SHA256_RAW, UUID_RAW


def invoice_pdf_path(owner_id: str, invoice_id: str, sha256: str) -> str:
    for name, value, pattern in (
        ("owner_id", owner_id, UUID_RAW),
        ("invoice_id", invoice_id, UUID_RAW),
        ("sha256", sha256, SHA256_RAW),
    ):
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise ValueError(f"{name} no tiene el formato esperado.")
    return f"{owner_id}/{invoice_id}-{sha256[:PDF_HASH_PREFIX]}.pdf"


def pdf_path_owner(path: str) -> str | None:
    """La carpeta (dueño) de una ruta con la forma exacta, o `None` si no la tiene (sin lanzar nunca: una ruta rara es una denegación)."""
    if not isinstance(path, str) or PDF_PATH.fullmatch(path) is None:
        return None
    return path.split("/", 1)[0]
