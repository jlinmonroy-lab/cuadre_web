"""Firma del archivo (SPEC-W-002 T2-08): los primeros bytes tienen que ser los del tipo declarado.

Storage no mira el contenido ni cruza la extensión con el tipo (Anexo B.1), así que la comprobación es nuestra y ocurre en el
servidor antes de llamar al agente: un PDF que en realidad es otra cosa no se manda a leer.
"""


def matches(mime_type: str, head: bytes) -> bool:
    """¿Los primeros bytes (hasta 32) corresponden a `mime_type`?"""
    if mime_type == "application/pdf":
        return head.startswith(b"%PDF-")
    if mime_type == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return head.startswith(b"\x89PNG")
    if mime_type == "image/heic":
        return head[4:8] == b"ftyp"
    if mime_type == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False
