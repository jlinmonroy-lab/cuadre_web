"""Constantes de documentos (SPEC-W-002 §5.1, §5.2, D-03).

Varias existen también en SQL (la CHECK de `documents`, el bucket `documents` y las funciones `app.*`). No son variables de entorno a
propósito: subir un límite exige tocar esos tres sitios, así que una variable solo podría bajarlo y dejaría dos fuentes de verdad.
`tests/documents/test_limits.py` comprueba que los tres coinciden.
"""

from cuadre.agents import FailureCode

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MiB: CHECK de documents.size_bytes, file_size_limit del bucket y esta API

# Tipo permitido -> extensión de la ruta de Storage (`{owner_id}/{document_id}.{ext}`).
MIME_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/heic": "heic",
    "image/webp": "webp",
}
UNPREVIEWABLE_MIME_TYPES = frozenset({"image/heic"})  # los navegadores no los muestran: solo descarga

# Igual que private.document_processing_timeout(): un `processing` más viejo que esto se da por fallido.
PROCESSING_TIMEOUT_SECONDS = 120
READ_URL_SECONDS = 120  # URL firmada que recibe el agente (NFR-11: corta)
PREVIEW_URL_SECONDS = 60  # URL firmada de la vista previa
SIGNATURE_BYTES = 32  # lo que se lee del archivo para comprobar su firma; nunca se descarga entero

LIST_LIMIT = 200  # la paginación llegará con SPEC-W-003 (cuando haya documentos `registered`)

RETRY_AFTER_TOO_MANY_PROCESSING = 10  # segundos
RETRY_AFTER_STORAGE_UNAVAILABLE = 5

# Textos de cada motivo de fallo (§5.1). Nunca llevan la respuesta del agente.
FAILURE_MESSAGES: dict[FailureCode, str] = {
    FailureCode.unreadable: "No hemos podido leer el documento. Prueba con una foto más nítida o rellena los datos a mano.",
    FailureCode.unsupported_media_type: "Este tipo de archivo no se puede leer.",
    FailureCode.payload_too_large: "El archivo es demasiado grande para leerlo.",
    FailureCode.timeout: "La lectura ha tardado demasiado.",
    FailureCode.upstream_error: "El servicio de lectura no está disponible ahora. Puedes reintentarlo o rellenar los datos a mano.",
    FailureCode.agents_unavailable: "El servicio de lectura no está disponible ahora. Puedes reintentarlo o rellenar los datos a mano.",
    FailureCode.invalid_response: "La lectura ha devuelto datos que no se pueden usar.",
    FailureCode.internal: "No se ha podido completar la lectura.",
}
