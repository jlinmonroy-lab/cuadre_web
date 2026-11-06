"""Errores de documentos en `application/problem+json` (SPEC-W-002 §5.1). `detail` en español, sin datos de la persona."""

from cuadre.core.errors import ProblemError
from cuadre.documents.limits import RETRY_AFTER_STORAGE_UNAVAILABLE, RETRY_AFTER_TOO_MANY_PROCESSING


def unsupported_file_type() -> ProblemError:
    return ProblemError(
        415,
        "unsupported_file_type",
        "Tipo de archivo no admitido",
        "Solo se admiten archivos PDF, JPG, PNG, HEIC y WebP.",
    )


def file_too_large() -> ProblemError:
    return ProblemError(413, "file_too_large", "Archivo demasiado grande", "El archivo supera el máximo de 15 MB.")


def file_type_mismatch() -> ProblemError:
    return ProblemError(
        422,
        "file_type_mismatch",
        "El archivo no es del tipo indicado",
        "El contenido del archivo no coincide con su tipo. Se ha descartado: súbelo de nuevo.",
    )


def upload_missing() -> ProblemError:
    return ProblemError(
        409,
        "upload_missing",
        "Archivo no recibido",
        "Todavía no hemos recibido el archivo. Espera a que termine la subida e inténtalo de nuevo.",
    )


def upload_size_mismatch() -> ProblemError:
    return ProblemError(
        422,
        "upload_size_mismatch",
        "Tamaño inesperado",
        "El tamaño del archivo recibido no coincide con el indicado. Se ha descartado: súbelo de nuevo.",
    )


def document_not_found() -> ProblemError:
    return ProblemError(404, "document_not_found", "Documento no encontrado", "El documento no existe.")


def document_wrong_state() -> ProblemError:
    return ProblemError(
        409,
        "document_wrong_state",
        "Estado no válido",
        "Esa acción no se puede hacer con el documento en su estado actual.",
    )


def too_many_processing() -> ProblemError:
    return ProblemError(
        429,
        "too_many_processing",
        "Demasiadas lecturas en curso",
        "Ya hay 5 documentos leyéndose. Espera a que termine alguno e inténtalo de nuevo.",
        headers={"Retry-After": str(RETRY_AFTER_TOO_MANY_PROCESSING)},
    )


def storage_unavailable() -> ProblemError:
    return ProblemError(
        503,
        "storage_unavailable",
        "Almacenamiento no disponible",
        "El almacenamiento de archivos no responde ahora mismo. Inténtalo de nuevo en unos segundos.",
        headers={"Retry-After": str(RETRY_AFTER_STORAGE_UNAVAILABLE)},
    )


def invalid_filename() -> ProblemError:
    return ProblemError(
        422,
        "validation_error",
        "Datos no válidos",
        "Revisa los datos enviados.",
        extra={"errors": [{"loc": "body.filename", "msg": "El nombre del archivo no es válido."}]},
    )
