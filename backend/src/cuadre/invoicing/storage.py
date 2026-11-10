"""Storage del PDF de las facturas (SPEC-W-007 §5.2 y §5.4, D-03, D-10, B.1-C). Siempre con el JWT de la persona: nunca la clave de servicio.

El bucket privado `invoices` guarda un PDF por factura en `{owner_id}/{invoice_id}-{sha256[:16]}.pdf`. Ese prefijo de la huella hace la subida
IDEMPOTENTE: el mismo contenido da siempre la misma ruta y un 409 de Storage significa «ya está». No hay `UPDATE` ni `DELETE` (políticas del hito 2):
nadie sustituye un PDF subido, y la huella que guarda `invoice_files` es la que manda al descargarlo.

`PdfStorage` y `LogoReader` son los dos trozos de `HttpStorage` que usa la facturación; así los dobles de las pruebas de documentos y de perfil no
tienen que implementarlos.
"""

import hashlib
from typing import Protocol

from cuadre.documents.storage import HttpStorage, ObjectInfo, UploadResult
from cuadre.invoicing.limits import PDF_PATH

BUCKET = "invoices"
PDF_CONTENT_TYPE = "application/pdf"
PDF_MAX_BYTES = 1_048_576  # 1 MiB, igual que el bucket y que la CHECK de `invoice_files`


class PdfStorage(Protocol):
    def upload(self, path: str, data: bytes, content_type: str, *, token: str) -> UploadResult:
        """Sube el PDF. «exists» si ya estaba (no es un error)."""
        ...

    def download(self, path: str, *, token: str, max_bytes: int) -> bytes:
        """El archivo entero, con un tope de `max_bytes + 1` bytes."""
        ...

    def object_info(self, path: str, *, token: str) -> ObjectInfo | None: ...


class LogoReader(Protocol):
    def download(self, path: str, *, token: str, max_bytes: int) -> bytes:
        """El logo entero (`logos`), con un tope de `max_bytes + 1` bytes."""
        ...


def invoice_storage(supabase_url: str) -> HttpStorage:
    """El Storage real del bucket `invoices`: solo acepta rutas con la forma exacta de `PDF_PATH`."""
    return HttpStorage(supabase_url, bucket=BUCKET, path=PDF_PATH)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
