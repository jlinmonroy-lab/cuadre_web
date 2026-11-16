"""AC-08 a AC-12, AC-16 · Las tablas del chat y sus funciones (SPEC-W-004 §5.2, D-03, D-04, D-07, D-12, D-15).

Nada se escribe directamente: la persona envía con `app.append_chat_user_message`, la web guarda la respuesta del asistente una sola vez con
`app.append_chat_assistant_message`, se borra con `app.delete_chat_conversation` y se valora con `app.rate_chat_message`. Los mensajes son inmutables y
solo desaparecen con su conversación. Gestor y administrador no ven nada. La visibilidad por rol la prueba además la matriz de RLS.
"""

import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.rls.test_clients import run_while_holding
from tests.support import Cast, Outcome, Person, Pool, apply_scenario, attempt

LIMIT = 20


def say(
    pool: Pool,
    person: Person,
    content: str = "¿Qué mención lleva una factura a una empresa alemana?",
    *,
    conversation: Any = None,
    title: str = "Mención en facturas a la UE",
    limit: int = LIMIT,
) -> Outcome:
    return attempt(
        pool,
        person,
        "select conversation_id, message_id from app.append_chat_user_message(%s, %s, %s, %s)",
        (conversation, content, title, limit),
    )


def started(pool: Pool, person: Person, **kwargs: Any) -> tuple[uuid.UUID, uuid.UUID]:
    out = say(pool, person, **kwargs)
    assert not out.error, out.message
    return out.rows[0]["conversation_id"], out.rows[0]["message_id"]


def answer(
    pool: Pool,
    person: Person,
    conversation: Any,
    *,
    message_id: Any = None,
    content: str = "Debe llevar la mención «Inversión del sujeto pasivo».",
    status: str = "complete",
    finish_reason: str | None = "stop",
    trace_id: str | None = "trc_synthetic_0001",
    has_source: bool | None = True,
    citations: str = "[]",
    abstention: str | None = None,
) -> Outcome:
    return attempt(
        pool,
        person,
        "select app.append_chat_assistant_message(%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)",
        (
            conversation,
            message_id or uuid.uuid4(),
            content,
            status,
            finish_reason,
            trace_id,
            has_source,
            citations,
            abstention,
        ),
    )


def replied(pool: Pool, person: Person, conversation: Any, **kwargs: Any) -> uuid.UUID:
    message_id = kwargs.pop("message_id", None) or uuid.uuid4()
    out = answer(pool, person, conversation, message_id=message_id, **kwargs)
    assert not out.error, out.message
    return message_id


def rate(pool: Pool, person: Person, message: Any, rating: str = "up", reason: str | None = None) -> Outcome:
    return attempt(pool, person, "select app.rate_chat_message(%s, %s, %s)", (message, rating, reason))


def conversations_of(admin: Connection[DictRow], owner: Any) -> list[dict[str, Any]]:
    return admin.execute(
        "select id, title, created_at, last_message_at from public.chat_conversations where owner_id = %s order by created_at",
        (owner,),
    ).fetchall()


def last_activity(admin: Connection[DictRow], conversation: Any) -> Any:
    row = admin.execute(
        "select last_message_at from public.chat_conversations where id = %s", (conversation,)
    ).fetchone()
    assert row is not None
    return row["last_message_at"]


def messages_of(admin: Connection[DictRow], conversation: Any) -> list[dict[str, Any]]:
    return admin.execute(
        "select * from public.chat_messages where conversation_id = %s order by created_at, id", (conversation,)
    ).fetchall()


def feedback_of(admin: Connection[DictRow], message: Any) -> dict[str, Any] | None:
    return admin.execute("select rating, reason from public.chat_feedback where message_id = %s", (message,)).fetchone()


def old_user_messages(admin: Connection[DictRow], owner: Any, conversation: Any, count: int, *, hours: float) -> None:
    """Mensajes de la persona de hace `hours` horas, puestos por `admin` (en SQL no se puede fijar `now()`)."""
    for _ in range(count):
        admin.execute(
            "insert into public.chat_messages (conversation_id, owner_id, role, content, created_at) "
            "values (%s, %s, 'user', 'antiguo', now() - make_interval(secs => %s))",
            (conversation, owner, hours * 3600),
        )


# --- El mensaje de la persona ----------------------------------------------------------------------------------------------------------


def test_the_first_message_creates_the_conversation_with_its_title(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, message = started(app_pool, cast.alicia)
    [row] = conversations_of(admin, cast.alicia.id)
    assert row["id"] == conversation and row["title"] == "Mención en facturas a la UE"
    [stored] = messages_of(admin, conversation)
    assert stored["id"] == message and stored["role"] == "user" and stored["status"] == "complete"
    assert stored["content"].startswith("¿Qué mención")
    assert stored["finish_reason"] is None and stored["trace_id"] is None and stored["has_source"] is None
    assert stored["citations"] == [] and stored["abstention"] is None


def test_a_later_message_joins_the_conversation_and_moves_its_last_activity(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    admin.execute(
        "update public.chat_conversations set last_message_at = now() - interval '1 day' where id = %s", (conversation,)
    )
    a_day_ago = last_activity(admin, conversation)
    second = started(app_pool, cast.alicia, conversation=conversation, content="¿Y a una de fuera de la UE?")
    assert second[0] == conversation
    assert len(conversations_of(admin, cast.alicia.id)) == 1
    assert len(messages_of(admin, conversation)) == 2
    [row] = conversations_of(admin, cast.alicia.id)
    assert (
        last_activity(admin, conversation) - a_day_ago
    ).total_seconds() > 60 * 60 * 23  # avanzó de hace un día a ahora
    assert row["title"] == "Mención en facturas a la UE"  # el título no cambia con los mensajes siguientes


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_gestores_and_admins_cannot_use_any_chat_function(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    person = cast[who]
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert say(app_pool, person).sqlstate == "42501"
    assert answer(app_pool, person, conversation).sqlstate == "42501"
    assert attempt(app_pool, person, "select app.delete_chat_conversation(%s)", (conversation,)).sqlstate == "42501"
    assert rate(app_pool, person, message).sqlstate == "42501"
    assert len(messages_of(admin, conversation)) == 2


def test_a_suspended_account_cannot_use_any_chat_function(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert say(app_pool, cast.alicia).sqlstate == "42501"
    assert say(app_pool, cast.alicia, conversation=conversation).sqlstate == "42501"
    assert answer(app_pool, cast.alicia, conversation).sqlstate == "42501"
    assert (
        attempt(app_pool, cast.alicia, "select app.delete_chat_conversation(%s)", (conversation,)).sqlstate == "42501"
    )
    assert rate(app_pool, cast.alicia, message).sqlstate == "42501"
    assert len(messages_of(admin, conversation)) == 2


def test_a_conversation_of_somebody_else_or_a_missing_one_is_not_found(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    for target in (conversation, uuid.uuid4()):
        out = say(app_pool, cast.beto, conversation=target)
        assert out.sqlstate == "P0001" and out.message == "conversation_not_found"
    assert len(messages_of(admin, conversation)) == 1
    assert conversations_of(admin, cast.beto.id) == []


@pytest.mark.parametrize("content", ["", "   ", "\n\t "])
def test_an_empty_message_is_refused_and_leaves_nothing_behind(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, content: str
) -> None:
    out = say(app_pool, cast.alicia, content)
    assert out.constraint == "chat_messages_user_shape"
    assert conversations_of(admin, cast.alicia.id) == []  # ni la conversación a medias


def test_a_message_over_the_contract_length_is_refused(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert say(app_pool, cast.alicia, "a" * 8001).constraint == "chat_messages_content_length"
    assert not say(app_pool, cast.alicia, "a" * 8000).error
    assert len(conversations_of(admin, cast.alicia.id)) == 1


@pytest.mark.parametrize("title", ["", "t" * 81])
def test_a_title_outside_one_to_eighty_characters_is_refused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, title: str
) -> None:
    assert say(app_pool, cast.alicia, title=title).constraint == "chat_conversations_title_length"
    assert conversations_of(admin, cast.alicia.id) == []


# --- El tope por hora (AC-16, D-12) ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("limit", [0, -1, 1001, None])
def test_a_limit_outside_one_to_a_thousand_is_refused(app_pool: Pool, cast: Cast, limit: int | None) -> None:
    out = attempt(app_pool, cast.alicia, "select app.append_chat_user_message(null, 'hola', 'Hola', %s)", (limit,))
    assert out.sqlstate == "P0001" and out.message == "invalid_hourly_limit"


def test_the_message_over_the_limit_is_refused_and_not_saved(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia, limit=3)
    assert not say(app_pool, cast.alicia, conversation=conversation, limit=3).error
    assert not say(app_pool, cast.alicia, conversation=conversation, limit=3).error
    out = say(app_pool, cast.alicia, conversation=conversation, limit=3)
    assert out.sqlstate == "P0001" and out.message == "chat_rate_limited"
    assert len(messages_of(admin, conversation)) == 3  # el cuarto no se guardó
    refused_new = say(app_pool, cast.alicia, limit=3)  # tampoco crea una conversación nueva
    assert refused_new.message == "chat_rate_limited"
    assert len(conversations_of(admin, cast.alicia.id)) == 1


def test_messages_from_over_an_hour_ago_do_not_count(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia, limit=3)
    old_user_messages(admin, cast.alicia.id, conversation, 5, hours=1.5)
    assert not say(app_pool, cast.alicia, conversation=conversation, limit=3).error  # son 2 en la última hora
    assert not say(app_pool, cast.alicia, conversation=conversation, limit=3).error  # 3: justo el tope
    assert say(app_pool, cast.alicia, conversation=conversation, limit=3).message == "chat_rate_limited"


def test_a_message_just_inside_the_hour_does_count(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia, limit=2)
    old_user_messages(admin, cast.alicia.id, conversation, 1, hours=0.9)
    assert say(app_pool, cast.alicia, conversation=conversation, limit=2).message == "chat_rate_limited"


def test_the_answers_of_the_assistant_do_not_count_towards_the_limit(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia, limit=2)
    for _ in range(4):
        replied(app_pool, cast.alicia, conversation)
    assert not say(app_pool, cast.alicia, conversation=conversation, limit=2).error


def test_the_limit_is_per_person(app_pool: Pool, cast: Cast) -> None:
    started(app_pool, cast.alicia, limit=1)
    assert say(app_pool, cast.alicia, limit=1).message == "chat_rate_limited"
    assert not say(app_pool, cast.beto, limit=1).error


def test_two_sends_at_the_limit_in_the_same_conversation_do_not_both_get_through(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """AC-16. En la misma conversación ya serializa el bloqueo de su fila; esta prueba fija ese comportamiento."""
    conversation, _ = started(app_pool, cast.alicia, limit=2)
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        "append_chat_user_message",
        (conversation, "primero", "T", 2),
        "append_chat_user_message",
        (conversation, "segundo", "T", 2),
    )
    assert waited, "el segundo envío no esperó al primero"
    assert second.message == "chat_rate_limited"
    assert len(messages_of(admin, conversation)) == 2


def test_two_new_conversations_at_the_limit_at_the_same_time_do_not_both_get_through(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """AC-16. Con conversaciones nuevas no hay fila común que bloquear: sin el cerrojo asesor por persona, los dos contarían 1 y entrarían (límite 2)."""
    started(app_pool, cast.alicia, limit=2)
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        "append_chat_user_message",
        (None, "primero", "Primera", 2),
        "append_chat_user_message",
        (None, "segundo", "Segunda", 2),
    )
    assert waited, "el segundo envío no esperó al primero"
    assert second.message == "chat_rate_limited"
    assert len(conversations_of(admin, cast.alicia.id)) == 2
    count = admin.execute(
        "select count(*) as n from public.chat_messages where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert count == {"n": 2}


def test_the_lock_is_per_person_so_somebody_else_does_not_wait(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        "append_chat_user_message",
        (None, "primero", "T", 2),
        "append_chat_user_message",
        (None, "de otra persona", "T", 2),
        other=cast.beto,
    )
    assert not waited and not second.error
    assert len(conversations_of(admin, cast.beto.id)) == 1


# --- La respuesta del asistente ---------------------------------------------------------------------------------------------------------


def test_the_answer_is_saved_once_with_its_sources_and_moves_the_last_activity(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    admin.execute(
        "update public.chat_conversations set last_message_at = now() - interval '1 day' where id = %s", (conversation,)
    )
    a_day_ago = last_activity(admin, conversation)
    citation = '[{"id": "1", "title": "Real Decreto 1619/2012", "publisher": "BOE", "url": "https://www.boe.es/x", "valid_as_of": "2026-09-01"}]'
    message = replied(app_pool, cast.alicia, conversation, citations=citation)
    _, stored = messages_of(admin, conversation)
    assert stored["id"] == message and stored["role"] == "assistant" and stored["status"] == "complete"
    assert (
        stored["finish_reason"] == "stop"
        and stored["trace_id"] == "trc_synthetic_0001"
        and stored["has_source"] is True
    )
    assert stored["citations"][0]["publisher"] == "BOE"
    assert (last_activity(admin, conversation) - a_day_ago).total_seconds() > 60 * 60 * 23


def test_an_abstention_keeps_its_referral_and_has_no_source_flag(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    replied(
        app_pool,
        cast.alicia,
        conversation,
        status="abstained",
        finish_reason="abstained",
        has_source=None,
        abstention='{"reason": "professional_judgment", "referral": "gestor"}',
    )
    stored = messages_of(admin, conversation)[1]
    assert (
        stored["status"] == "abstained"
        and stored["abstention"]["referral"] == "gestor"
        and stored["has_source"] is None
    )


@pytest.mark.parametrize(
    ("status", "finish_reason", "has_source"),
    [
        ("complete", "stop", False),
        ("complete", "length", True),
        ("error", "error", None),
        ("error", None, None),
        ("interrupted", None, None),
    ],
)
def test_the_states_an_answer_can_end_in(
    app_pool: Pool,
    admin: Connection[DictRow],
    cast: Cast,
    status: str,
    finish_reason: str | None,
    has_source: bool | None,
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    out = answer(
        app_pool,
        cast.alicia,
        conversation,
        status=status,
        finish_reason=finish_reason,
        has_source=has_source,
        trace_id=None,
    )
    assert not out.error, out.message
    assert messages_of(admin, conversation)[1]["status"] == status


@pytest.mark.parametrize(
    ("status", "finish_reason", "has_source", "constraint"),
    [
        ("complete", None, True, "chat_messages_status_matches_finish"),  # un nulo no puede colarse por el CHECK
        ("complete", "abstained", True, "chat_messages_status_matches_finish"),
        ("abstained", "stop", None, "chat_messages_status_matches_finish"),
        ("abstained", None, None, "chat_messages_status_matches_finish"),
        ("interrupted", "stop", None, "chat_messages_status_matches_finish"),
        ("error", "stop", None, "chat_messages_status_matches_finish"),
        ("complete", "stop", True, None),
        ("abstained", "abstained", True, "chat_messages_source_only_when_complete"),
        ("interrupted", None, False, "chat_messages_source_only_when_complete"),
        ("done", "stop", None, "chat_messages_status_known"),
        ("complete", "cut", None, "chat_messages_finish_reason_known"),
    ],
)
def test_incoherent_states_are_refused(
    app_pool: Pool,
    admin: Connection[DictRow],
    cast: Cast,
    status: str,
    finish_reason: str | None,
    has_source: bool | None,
    constraint: str | None,
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    out = answer(app_pool, cast.alicia, conversation, status=status, finish_reason=finish_reason, has_source=has_source)
    assert out.constraint == constraint
    assert len(messages_of(admin, conversation)) == (2 if constraint is None else 1)


def test_citations_must_be_an_array_and_the_abstention_an_object(app_pool: Pool, cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    assert (
        answer(app_pool, cast.alicia, conversation, citations='{"a": 1}').constraint == "chat_messages_citations_array"
    )
    assert answer(app_pool, cast.alicia, conversation, abstention="[1]").constraint == "chat_messages_abstention_object"


def test_the_answer_has_a_contract_length_and_a_trace_length(app_pool: Pool, cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    assert answer(app_pool, cast.alicia, conversation, content="a" * 8001).constraint == "chat_messages_content_length"
    assert answer(app_pool, cast.alicia, conversation, trace_id="t" * 201).constraint == "chat_messages_trace_id_length"
    assert not answer(
        app_pool, cast.alicia, conversation, content="", status="interrupted", finish_reason=None, has_source=None
    ).error


def test_an_answer_with_a_repeated_id_is_refused(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert answer(app_pool, cast.alicia, conversation, message_id=message).sqlstate == "23505"
    assert len(messages_of(admin, conversation)) == 2


def test_nobody_can_answer_in_somebody_elses_conversation(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    for target in (conversation, uuid.uuid4()):
        out = answer(app_pool, cast.beto, target)
        assert out.sqlstate == "P0001" and out.message == "conversation_not_found"
    assert len(messages_of(admin, conversation)) == 1


# --- Los mensajes son inmutables (D-07) ------------------------------------------------------------------------------------------------


def test_a_message_cannot_be_changed_or_deleted_on_its_own_not_even_by_the_database_owner(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, message = started(app_pool, cast.alicia)
    for sql in (
        "update public.chat_messages set content = 'otra cosa' where id = %s",
        "update public.chat_messages set status = 'error' where id = %s",
        "delete from public.chat_messages where id = %s",
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="chat_message_immutable"):
            admin.execute(sql, (message,))
    with pytest.raises(psycopg.errors.RaiseException, match="chat_message_immutable"):
        admin.execute("truncate public.chat_messages, public.chat_feedback")  # sola, la frena antes la clave foránea
    [stored] = messages_of(admin, conversation)
    assert stored["content"].startswith("¿Qué mención") and stored["status"] == "complete"


def test_deleting_the_conversation_takes_its_messages_and_ratings_with_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message).error
    other, _ = started(app_pool, cast.alicia, content="otra duda")
    out = attempt(app_pool, cast.alicia, "select app.delete_chat_conversation(%s)", (conversation,))
    assert not out.error, out.message
    assert messages_of(admin, conversation) == [] and feedback_of(admin, message) is None
    assert [c["id"] for c in conversations_of(admin, cast.alicia.id)] == [other]
    assert len(messages_of(admin, other)) == 1


def test_deleting_the_conversation_directly_also_works_but_a_loose_message_still_does_not(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, message = started(app_pool, cast.alicia)
    with pytest.raises(psycopg.errors.RaiseException, match="chat_message_immutable"):
        admin.execute("delete from public.chat_messages where id = %s", (message,))
    admin.execute("delete from public.chat_conversations where id = %s", (conversation,))
    assert messages_of(admin, conversation) == []


def test_deleting_the_account_takes_the_whole_chat_with_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message).error
    kept, _ = started(app_pool, cast.beto)
    admin.execute("delete from auth.users where id = %s", (cast.alicia.id,))
    assert conversations_of(admin, cast.alicia.id) == [] and messages_of(admin, conversation) == []
    assert feedback_of(admin, message) is None
    assert len(messages_of(admin, kept)) == 1


def test_deleting_a_conversation_that_is_not_yours_or_does_not_exist_is_not_found(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    for target in (conversation, uuid.uuid4()):
        out = attempt(app_pool, cast.beto, "select app.delete_chat_conversation(%s)", (target,))
        assert out.sqlstate == "P0001" and out.message == "conversation_not_found"
    assert len(messages_of(admin, conversation)) == 1


# --- La valoración (AC-08, D-04) -------------------------------------------------------------------------------------------------------


def test_a_person_rates_an_answer_and_can_change_their_mind(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message, "up").error
    assert feedback_of(admin, message) == {"rating": "up", "reason": None}
    assert not rate(app_pool, cast.alicia, message, "down", "no_source").error
    assert feedback_of(admin, message) == {"rating": "down", "reason": "no_source"}
    assert not rate(app_pool, cast.alicia, message, "up").error
    assert feedback_of(admin, message) == {"rating": "up", "reason": None}
    count = admin.execute("select count(*) as n from public.chat_feedback where message_id = %s", (message,)).fetchone()
    assert count == {"n": 1}


@pytest.mark.parametrize("reason", ["incorrect", "no_source", "not_helpful", "other"])
def test_every_reason_of_the_closed_list_is_accepted(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, reason: str
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message, "down", reason).error
    assert feedback_of(admin, message) == {"rating": "down", "reason": reason}


@pytest.mark.parametrize(
    ("rating", "reason"),
    [("down", None), ("down", "malo"), ("down", ""), ("up", "other"), ("up", "incorrect"), ("meh", None)],
)
def test_a_rating_without_its_reason_or_with_an_unknown_one_is_refused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, rating: str, reason: str | None
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    out = rate(app_pool, cast.alicia, message, rating, reason)
    assert out.constraint in {"chat_feedback_reason_matches_rating", "chat_feedback_rating_known"}
    assert feedback_of(admin, message) is None


def test_a_refused_change_keeps_the_previous_rating(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message, "up").error
    assert rate(app_pool, cast.alicia, message, "down", None).error
    assert feedback_of(admin, message) == {"rating": "up", "reason": None}


def test_only_the_answers_of_the_assistant_can_be_rated(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    conversation, own_question = started(app_pool, cast.alicia)
    for target in (own_question, uuid.uuid4()):
        out = rate(app_pool, cast.alicia, target)
        assert out.sqlstate == "P0001" and out.message == "message_not_found"
    count = admin.execute(
        "select count(*) as n from public.chat_feedback where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert count == {"n": 0}


def test_nobody_rates_the_answers_of_somebody_else(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    out = rate(app_pool, cast.beto, message)
    assert out.sqlstate == "P0001" and out.message == "message_not_found"  # no se distingue de «no existe»
    assert feedback_of(admin, message) is None


# --- Nadie escribe las tablas directamente ni ve lo de otra persona (AC-11, D-15) ---------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_writes_the_tables_directly_not_even_the_owner(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message).error
    person = cast[who]
    statements = (
        ("insert into public.chat_conversations (owner_id, title) values (%s, 'x')", (person.id,)),
        ("update public.chat_conversations set title = 'x'", None),
        ("delete from public.chat_conversations", None),
        (
            "insert into public.chat_messages (conversation_id, owner_id, role, content) values (%s, %s, 'user', 'x')",
            (conversation, person.id),
        ),
        ("update public.chat_messages set content = 'x'", None),
        ("delete from public.chat_messages", None),
        ("insert into public.chat_feedback (message_id, owner_id, rating) values (%s, %s, 'up')", (message, person.id)),
        ("update public.chat_feedback set rating = 'down', reason = 'other'", None),
        ("delete from public.chat_feedback", None),
        ("truncate public.chat_messages", None),
    )
    for sql, params in statements:
        assert attempt(app_pool, person, sql, params).sqlstate == "42501", sql
    assert len(messages_of(admin, conversation)) == 2
    assert feedback_of(admin, message) == {"rating": "up", "reason": None}


@pytest.mark.parametrize("table", ["chat_conversations", "chat_messages", "chat_feedback"])
def test_the_tables_have_forced_rls_one_read_policy_and_no_policy_for_gestores_or_admins(
    admin: Connection[DictRow], table: str
) -> None:
    row = admin.execute(
        "select relrowsecurity as rls, relforcerowsecurity as forced from pg_class where oid = %s::regclass",
        (f"public.{table}",),
    ).fetchone()
    assert row == {"rls": True, "forced": True}
    policies = admin.execute(
        "select policyname, cmd, roles::text as roles from pg_policies where tablename = %s", (table,)
    ).fetchall()
    assert [(p["policyname"], p["cmd"]) for p in policies] == [(f"{table}_select_owner", "SELECT")]
    assert policies[0]["roles"] == "{authenticated}"
    for role in ("anon", "service_role", "authenticated"):
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            granted = admin.execute(
                "select has_table_privilege(%s, %s, %s) as ok", (role, f"public.{table}", privilege)
            ).fetchone()
            assert granted == {"ok": False}, (role, privilege)


def test_everybody_sees_only_their_own_chat_and_gestores_and_admins_see_nothing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    conversation, _ = started(app_pool, cast.alicia)
    message = replied(app_pool, cast.alicia, conversation)
    assert not rate(app_pool, cast.alicia, message).error
    apply_scenario(
        app_pool, cast, "active"
    )  # Gina, la gestora de Alicia, tiene el vínculo activo: aun así no ve su chat
    for table in ("chat_conversations", "chat_messages", "chat_feedback"):
        counts = {}
        for who in ("alicia", "beto", "gina", "gus", "adan"):
            counts[who] = len(attempt(app_pool, cast[who], f"select * from public.{table}").rows)
        assert counts == {"alicia": counts["alicia"], "beto": 0, "gina": 0, "gus": 0, "adan": 0}, table
        assert counts["alicia"] >= 1


def test_the_functions_are_not_open_to_anonymous_callers(admin: Connection[DictRow]) -> None:
    for signature in (
        "app.append_chat_user_message(uuid, text, text, integer)",
        "app.append_chat_assistant_message(uuid, uuid, text, text, text, text, boolean, jsonb, jsonb)",
        "app.delete_chat_conversation(uuid)",
        "app.rate_chat_message(uuid, text, text)",
    ):
        for role, expected in (("anon", False), ("service_role", False), ("authenticated", True)):
            row = admin.execute("select has_function_privilege(%s, %s, 'EXECUTE') as ok", (role, signature)).fetchone()
            assert row == {"ok": expected}, (role, signature)
