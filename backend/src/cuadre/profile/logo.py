"""Reglas del logo (SPEC-W-005 §5.1, T5-06): tipo y tamaño declarados, y firma del archivo. Python puro; el archivo no entra aquí."""

from cuadre.profile.limits import JPEG_SIGNATURE, LOGO_MAX_BYTES, LOGO_TYPES, PNG_SIGNATURE


def extension_for(mime: object) -> str | None:
    """`png`, `jpg` o `webp`; `None` para cualquier otro tipo (SVG no: puede llevar scripts)."""
    return LOGO_TYPES.get(mime) if isinstance(mime, str) else None


def declared_problem(mime: object, size: object) -> str | None:
    """`None` si lo anunciado vale; si no, `unsupported_type` (415), `too_large` (413) o `invalid` (422). El tipo se mira antes que el tamaño."""
    if extension_for(mime) is None:
        return "unsupported_type"
    if type(size) is not int or size < 1:
        return "invalid"
    if size > LOGO_MAX_BYTES:
        return "too_large"
    return None


def signature_matches(mime: object, head: object) -> bool:
    """¿Los primeros bytes son los de ese tipo? PNG: 8 bytes; JPEG: 3; WebP: `RIFF`, 4 bytes de tamaño y `WEBP` (12)."""
    if not isinstance(head, bytes | bytearray):
        return False
    data = bytes(head)
    if mime == "image/png":
        return data.startswith(PNG_SIGNATURE)
    if mime == "image/jpeg":
        return data.startswith(JPEG_SIGNATURE)
    if mime == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False
