"""SQL explícito del chat (SPEC-W-004 §5.2, ADR-0003). Cada función recibe una conexión que ya lleva la identidad de la persona (`user_transaction`).

Todo lo que se escribe pasa por las funciones `app.*` de la migración `20261116100300_chat_functions.sql`; las lecturas filtran por el dueño además
de la RLS. Los errores de esas funciones llevan un código estable en el mensaje.
"""

from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.chat import errors, limits
from cuadre.chat.models import ConversationSummary, MessageOut
from cuadre.chat.types import ContextRow, Outcome
from cuadre.core.errors import ProblemError, forbidden

_PROBLEMS = {
    "conversation_not_found": errors.conversation_not_found,
    "message_not_found": errors.message_not_found,
    "chat_rate_limited": errors.chat_rate_limited,
}
# `invalid_hourly_limit` no está: es un error de programación (el límite es una constante nuestra) y debe verse como un 500.


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` -> problem+json. `None` si no es uno de ellos (se propaga y es un 500)."""
    if exc.sqlstate == "42501":
        return forbidden()
    if exc.sqlstate == "P0001":
        factory = _PROBLEMS.get(exc.diag.message_primary or "")
        return factory() if factory is not None else None
    return None


# --- Escritura -------------------------------------------------------------------------------------------------------------


def append_user_message(
    conn: Connection[DictRow], conversation_id: UUID | None, content: str, title: str, hourly_limit: int
) -> tuple[UUID, UUID]:
    """Guarda el mensaje de la persona (y crea la conversación si `conversation_id` es nulo) con el tope por hora. Devuelve ambos ids."""
    row = conn.execute(
        "SELECT conversation_id, message_id FROM app.append_chat_user_message(%s, %s, %s, %s)",
        (conversation_id, content, title, hourly_limit),
    ).fetchone()
    assert row is not None
    return row["conversation_id"], row["message_id"]


def append_assistant_message(
    conn: Connection[DictRow],
    conversation_id: UUID,
    message_id: UUID,
    content: str,
    outcome: Outcome,
    trace_id: str | None,
    citations: list[dict[str, Any]],
    abstention: dict[str, Any] | None,
) -> None:
    conn.execute(
        "SELECT app.append_chat_assistant_message(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            conversation_id,
            message_id,
            content,
            outcome.status,
            outcome.finish_reason,
            trace_id or None,
            outcome.has_source,
            Jsonb(citations),
            Jsonb(abstention) if abstention is not None else None,
        ),
    )


def delete_conversation(conn: Connection[DictRow], conversation_id: UUID) -> None:
    conn.execute("SELECT app.delete_chat_conversation(%s)", (conversation_id,))


def rate_message(conn: Connection[DictRow], message_id: UUID, rating: str, reason: str | None) -> None:
    conn.execute("SELECT app.rate_chat_message(%s, %s, %s)", (message_id, rating, reason))


# --- Lectura ---------------------------------------------------------------------------------------------------------------


def context_rows(conn: Connection[DictRow], conversation_id: UUID) -> list[ContextRow]:
    """Los últimos `CONTEXT_MESSAGES` mensajes de la conversación, en orden cronológico."""
    rows = conn.execute(
        """
        SELECT role, content, status FROM (
          SELECT role, content, status, created_at, id FROM public.chat_messages
           WHERE conversation_id = %s AND owner_id = (SELECT auth.uid())
           ORDER BY created_at DESC, id DESC LIMIT %s
        ) latest ORDER BY created_at, id
        """,
        (conversation_id, limits.CONTEXT_MESSAGES),
    ).fetchall()
    return [ContextRow(r["role"], r["content"], r["status"]) for r in rows]


def has_gestor(conn: Connection[DictRow]) -> bool:
    """¿Tiene la persona un gestor vinculado ahora mismo? Solo el vínculo `active`; la política de dueño de `gestor_access` ya se lo permite leer."""
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM public.gestor_access WHERE owner_id = (SELECT auth.uid()) AND status = 'active') AS has_gestor"
    ).fetchone()
    assert row is not None
    return bool(row["has_gestor"])


def retry_after_seconds(conn: Connection[DictRow], hourly_limit: int) -> int:
    """Segundos hasta que el mensaje más antiguo de los que cuentan salga de la ventana de una hora (y se libere un hueco)."""
    row = conn.execute(
        """
        SELECT COALESCE(
                 GREATEST(1, LEAST(%s, CEIL(EXTRACT(EPOCH FROM (min(t.created_at) + interval '1 hour' - now())))::int)),
                 %s) AS seconds
          FROM (SELECT created_at FROM public.chat_messages
                 WHERE owner_id = (SELECT auth.uid()) AND role = 'user' AND created_at > now() - interval '1 hour'
                 ORDER BY created_at DESC LIMIT %s) t
        """,
        (limits.MAX_RETRY_AFTER_SECONDS, limits.RETRY_AFTER_FALLBACK_SECONDS, hourly_limit),
    ).fetchone()
    assert row is not None
    return int(row["seconds"])


def list_conversations(conn: Connection[DictRow]) -> list[ConversationSummary]:
    rows = conn.execute(
        """
        SELECT id, title, created_at, last_message_at FROM public.chat_conversations
         WHERE owner_id = (SELECT auth.uid()) ORDER BY last_message_at DESC, id DESC LIMIT %s
        """,
        (limits.LIST_LIMIT,),
    ).fetchall()
    return [ConversationSummary.model_validate(r) for r in rows]


def get_conversation_row(conn: Connection[DictRow], conversation_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, title, created_at, last_message_at FROM public.chat_conversations
         WHERE id = %s AND owner_id = (SELECT auth.uid())
        """,
        (conversation_id,),
    ).fetchone()


def thread(conn: Connection[DictRow], conversation_id: UUID) -> list[MessageOut]:
    """Los mensajes de la conversación con su valoración, en orden; si hay más de `THREAD_LIMIT`, los más recientes."""
    rows = conn.execute(
        """
        SELECT * FROM (
          SELECT m.id, m.role, m.content, m.status, m.finish_reason, m.trace_id, m.has_source, m.citations, m.abstention,
                 m.created_at, f.rating, f.reason
            FROM public.chat_messages m LEFT JOIN public.chat_feedback f ON f.message_id = m.id
           WHERE m.conversation_id = %s AND m.owner_id = (SELECT auth.uid())
           ORDER BY m.created_at DESC, m.id DESC LIMIT %s
        ) latest ORDER BY created_at, id
        """,
        (conversation_id, limits.THREAD_LIMIT),
    ).fetchall()
    return [MessageOut.model_validate(r) for r in rows]
