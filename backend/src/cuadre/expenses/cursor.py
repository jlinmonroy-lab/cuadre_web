"""Cursor opaco de la lista de gastos (SPEC-W-003 §5.3, AC-14).

Es la posición del último gasto entregado en el orden de la lista (`expense_date`, `created_at`, `id`, de más reciente a más antiguo):
base64url de un JSON `{"d": fecha, "c": creación, "i": id}`. Se lee con rigor (forma, tipos y formato exactos) y cualquier otra cosa es
`invalid_cursor`. No lleva firma: no hay ningún secreto en la configuración y un cursor fabricado solo mueve una ventana sobre las filas de
quien pregunta, que la RLS y el filtro de dueño ya limitan.
"""

import base64
import json
import re
from datetime import UTC, date, datetime
from uuid import UUID

from cuadre.expenses import errors

Position = tuple[date, datetime, UUID]

_ALPHABET = re.compile(r"[A-Za-z0-9_-]{1,200}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def encode(position: Position) -> str:
    day, created, expense_id = position
    payload = {"d": day.isoformat(), "c": created.astimezone(UTC).isoformat(), "i": str(expense_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode(text: str) -> Position:
    try:
        if _ALPHABET.fullmatch(text) is None:
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))
        if not isinstance(payload, dict) or set(payload) != {"d", "c", "i"}:
            raise ValueError
        raw_day, raw_created, raw_id = payload["d"], payload["c"], payload["i"]
        if not all(isinstance(v, str) for v in (raw_day, raw_created, raw_id)) or _DATE.fullmatch(raw_day) is None:
            raise ValueError
        created = datetime.fromisoformat(raw_created)
        expense_id = UUID(raw_id)
        if created.tzinfo is None or str(expense_id) != raw_id:
            raise ValueError
        return date.fromisoformat(raw_day), created, expense_id
    except (ValueError, TypeError, UnicodeError):
        raise errors.invalid_cursor() from None
