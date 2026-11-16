"""Los eventos que ve el navegador, como `text/event-stream` (SPEC-W-004 §5.3, D-06)."""

import json

from cuadre.chat.types import OutEvent


def encode(event: OutEvent) -> bytes:
    """`event: <nombre>` y `data: <json en una línea>`. El JSON escapa los saltos de línea, así que un texto no puede partir el evento."""
    name, data = event
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {payload}\n\n".encode()
