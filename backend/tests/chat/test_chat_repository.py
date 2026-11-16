"""Lecturas del repositorio del chat con la base de datos real (SPEC-W-004 §5.2): el contexto y el aislamiento por persona."""

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.chat import limits, repository
from cuadre.db import user_transaction
from tests.support import Cast, Pool, attempt


def started(app_pool: Pool, cast: Cast) -> str:
    out = attempt(
        app_pool,
        cast.alicia,
        "select conversation_id from app.append_chat_user_message(%s, %s, %s, %s)",
        (None, "pregunta 0", "Título", 20),
    )
    assert not out.error, out.message
    return str(out.rows[0]["conversation_id"])


def test_the_context_reads_only_the_last_rows_in_chronological_order(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation = started(app_pool, cast)
    for n in range(1, 71):
        admin.execute(
            "insert into public.chat_messages (conversation_id, owner_id, role, content, created_at) "
            "values (%s, %s, 'user', %s, now() - interval '2 days' + make_interval(secs => %s))",
            (conversation, cast.alicia.id, f"antiguo {n}", n),
        )
    with user_transaction(app_pool, cast.alicia.id) as conn:
        rows = repository.context_rows(conn, conversation)  # type: ignore[arg-type]
    assert len(rows) == limits.CONTEXT_MESSAGES
    # 70 antiguos y la pregunta nueva son 71 filas: se leen las 50 últimas, es decir, los antiguos del 22 al 70 y la nueva.
    assert rows[-1].content == "pregunta 0" and rows[0].content == "antiguo 22"
    assert [r.content for r in rows[:-1]] == [f"antiguo {n}" for n in range(22, 71)]


def test_a_person_never_reads_the_context_of_somebody_elses_conversation(app_pool: Pool, cast: Cast) -> None:
    conversation = started(app_pool, cast)
    with user_transaction(app_pool, cast.beto.id) as conn:
        assert repository.context_rows(conn, conversation) == []  # type: ignore[arg-type]
        assert repository.get_conversation_row(conn, conversation) is None  # type: ignore[arg-type]
        assert repository.thread(conn, conversation) == []  # type: ignore[arg-type]
        assert repository.list_conversations(conn) == []  # type: ignore[arg-type]
