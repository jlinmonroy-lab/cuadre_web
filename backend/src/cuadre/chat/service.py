"""El chat (SPEC-W-004 §5.4, D-06, D-07): guarda el mensaje de la persona, abre el flujo del agente, lo valida y lo reenvía, y guarda la respuesta.

Reglas que importan:

* **Nunca se retiene una conexión de la base de datos mientras se espera al agente.** Cada paso con la base abre su transacción corta (`_in_tx`).
* **La respuesta HTTP empieza con el primer frame del agente.** Si el agente falla antes (`open_stream`), la ruta responde un `503 problem+json`
  de verdad, con el mensaje de la persona ya guardado; después del primer frame, un fallo es un evento `error` dentro del flujo.
* **El mensaje del asistente se guarda una sola vez y ANTES del evento terminal** (`done`/`error`), para que el identificador que ve el navegador
  exista. Si el flujo se cierra antes (el navegador cortó), se guarda como `interrupted` con lo recibido, y eso se hace bajo un escudo de
  cancelación: sin él, un `await` dentro de un ámbito ya cancelado se cancela antes de empezar y no se guardaría nada.
* **Nada de lo que escribe la persona o responde el agente llega a un registro** (D-13): solo identificadores, códigos, cifras y duraciones.
"""

import logging
import time
from collections.abc import AsyncIterator, Callable
from uuid import UUID, uuid4

import anyio
import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool
from starlette.concurrency import run_in_threadpool

from cuadre.agents import AgentsClient, AgentsError
from cuadre.chat import errors, events, limits, repository, rules
from cuadre.chat.models import ConversationDetail, ConversationList, FeedbackBody, FeedbackOut
from cuadre.chat.types import Outcome, Prepared
from cuadre.core.auth import CurrentUser
from cuadre.core.clock import Clock, today_in_madrid
from cuadre.core.errors import ProblemError
from cuadre.db import user_transaction

logger = logging.getLogger("cuadre.chat")


class ChatService:
    def __init__(self, pool: ConnectionPool[Connection[DictRow]], agents: AgentsClient, clock: Clock) -> None:
        self.pool = pool
        self.agents = agents
        self.clock = clock

    # --- Utilidades -----------------------------------------------------------------------------------------------------

    def _in_tx[T](self, user: CurrentUser, work: Callable[[Connection[DictRow]], T]) -> T:
        """Una transacción corta con la identidad de la persona. Los errores de las funciones `app.*` salen como problem+json."""
        try:
            with user_transaction(self.pool, user.id, user.claims) as conn:
                return work(conn)
        except psycopg.Error as exc:
            problem = repository.translate_db_error(exc)
            if problem is None:
                raise
            raise problem from None

    # --- Conversaciones y valoración (síncronas: FastAPI las corre en su pool de hilos) ------------------------------------

    def list_conversations(self, user: CurrentUser) -> ConversationList:
        return ConversationList(items=self._in_tx(user, repository.list_conversations))

    def get_conversation(self, user: CurrentUser, conversation_id: UUID) -> ConversationDetail:
        def work(conn: Connection[DictRow]) -> ConversationDetail:
            row = repository.get_conversation_row(conn, conversation_id)
            if row is None:
                raise errors.conversation_not_found()
            return ConversationDetail(**row, messages=repository.thread(conn, conversation_id))

        return self._in_tx(user, work)

    def delete_conversation(self, user: CurrentUser, conversation_id: UUID) -> None:
        self._in_tx(user, lambda conn: repository.delete_conversation(conn, conversation_id))

    def rate_message(self, user: CurrentUser, message_id: UUID, body: FeedbackBody) -> FeedbackOut:
        self._in_tx(user, lambda conn: repository.rate_message(conn, message_id, body.rating, body.reason))
        return FeedbackOut(message_id=message_id, rating=body.rating, reason=body.reason)

    # --- Enviar un mensaje ------------------------------------------------------------------------------------------------

    def _begin(self, user: CurrentUser, conversation_id: UUID | None, message: str, hourly_limit: int) -> Prepared:
        """El mensaje de la persona guardado (con el tope por hora) y la petición para el agente, en una sola transacción corta."""
        title = rules.title_of(message)

        def work(conn: Connection[DictRow]) -> Prepared:
            conversation, message_id = repository.append_user_message(
                conn, conversation_id, message, title, hourly_limit
            )
            rows = repository.context_rows(conn, conversation)
            gestor = repository.has_gestor(conn)
            request = rules.build_request(conversation, rows, has_gestor=gestor, today=today_in_madrid(self.clock))
            return Prepared(conversation, message_id, request, gestor)

        try:
            return self._in_tx(user, work)
        except ProblemError as problem:
            if problem.code != "chat_rate_limited":
                raise
            # El `Retry-After` real sale de una lectura aparte: la transacción del envío se deshizo con el error.
            seconds = self._in_tx(user, lambda conn: repository.retry_after_seconds(conn, hourly_limit))
            raise errors.chat_rate_limited(seconds) from None

    async def open_stream(
        self, user: CurrentUser, request_id: str, conversation_id: UUID | None, content: str
    ) -> AsyncIterator[bytes]:
        """Guarda el mensaje, abre el flujo del agente y espera su primer frame. Devuelve el generador de eventos listo para enviarse.

        Todo lo que falla antes de devolver algo es un `ProblemError` (problem+json con su estado): validación, tope por hora y agente que no responde.
        """
        try:
            message = rules.clean_message(content)
        except rules.MessageEmpty:
            raise errors.message_empty() from None
        except rules.MessageTooLong:
            raise errors.message_too_long() from None
        return await self._open(user, request_id, message, conversation_id)

    async def _open(
        self, user: CurrentUser, request_id: str, message: str, conversation_id: UUID | None
    ) -> AsyncIterator[bytes]:
        started = time.monotonic_ns()
        prepared = await run_in_threadpool(self._begin, user, conversation_id, message, limits.MESSAGES_PER_HOUR)
        frames = self.agents.stream_chat(prepared.request, request_id=request_id)
        try:
            first = await anext(frames)
        except (AgentsError, StopAsyncIteration) as failure:
            code = failure.code.value if isinstance(failure, AgentsError) else "invalid_response"
            self._log(user, request_id, prepared.conversation_id, started, outcome=code, status="not_started")
            raise errors.agent_unavailable(prepared.conversation_id) from None
        except BaseException:
            await _close(frames)
            raise
        return self._events(user, request_id, prepared, frames, first, started)

    # --- El flujo ---------------------------------------------------------------------------------------------------------

    async def _events(
        self,
        user: CurrentUser,
        request_id: str,
        prepared: Prepared,
        frames: AsyncIterator[object],
        first: object,
        started: int,
    ) -> AsyncIterator[bytes]:
        reply = rules.ReplyAccumulator(has_gestor=prepared.has_gestor)
        message_id = uuid4()
        saved = False
        final: Outcome | None = None
        try:
            yield events.encode(
                (
                    "start",
                    {
                        "conversation_id": str(prepared.conversation_id),
                        "user_message_id": str(prepared.user_message_id),
                        "message_id": str(message_id),
                    },
                )
            )
            frame = first
            while True:
                for event in reply.accept(frame):  # type: ignore[arg-type]
                    yield events.encode(event)
                if reply.terminal is not None:
                    break
                try:
                    frame = await anext(frames)  # type: ignore[call-overload]
                except StopAsyncIteration:
                    reply.fail("agent_error")  # el flujo se cerró sin `done` ni `error`
                    break
                except AgentsError as failure:
                    reply.fail(rules.error_code_for_failure(failure.code.value))
                    break
                except (
                    Exception
                ) as unexpected:  # un fallo nuestro o del doble de pruebas: no se lleva el flujo por delante
                    logger.error(
                        "chat_stream_failed",
                        extra={
                            "request_id": request_id,
                            "conversation_id": str(prepared.conversation_id),
                            "exc_type": type(unexpected).__name__,
                        },
                    )
                    reply.fail("agent_unavailable")
                    break
            final = reply.outcome()
            saved = await self._save_quietly(user, request_id, prepared, message_id, reply, final)
            if not saved:
                yield events.encode(rules.unavailable_event(message_id))
                return
            yield events.encode(rules.terminal_event(final, message_id=message_id, trace_id=reply.trace_id))
        finally:
            with anyio.CancelScope(shield=True):
                if not saved:
                    # El flujo se cortó (o no se pudo guardar): lo recibido hasta ahora se guarda, bajo escudo (ver el docstring del módulo).
                    final = reply.outcome()
                    saved = await self._save_quietly(user, request_id, prepared, message_id, reply, final)
                await _close(frames)
            self._log(
                user,
                request_id,
                prepared.conversation_id,
                started,
                outcome=final.status if final is not None else "interrupted",
                status="saved" if saved else "not_saved",
                reply=reply,
                final=final,
            )

    def _save(
        self, user: CurrentUser, prepared: Prepared, message_id: UUID, reply: rules.ReplyAccumulator, outcome: Outcome
    ) -> None:
        self._in_tx(
            user,
            lambda conn: repository.append_assistant_message(
                conn,
                prepared.conversation_id,
                message_id,
                reply.text,
                outcome,
                reply.trace_id,
                reply.citations,
                reply.abstention,
            ),
        )

    async def _save_quietly(
        self,
        user: CurrentUser,
        request_id: str,
        prepared: Prepared,
        message_id: UUID,
        reply: rules.ReplyAccumulator,
        outcome: Outcome,
    ) -> bool:
        try:
            await run_in_threadpool(self._save, user, prepared, message_id, reply, outcome)
        except Exception as failure:
            # Sin el mensaje de la excepción: el de la base de datos puede citar valores.
            logger.error(
                "chat_save_failed",
                extra={
                    "request_id": request_id,
                    "conversation_id": str(prepared.conversation_id),
                    "exc_type": type(failure).__name__,
                },
            )
            return False
        return True

    def _log(
        self,
        user: CurrentUser,
        request_id: str,
        conversation_id: UUID,
        started: int,
        *,
        outcome: str,
        status: str,
        reply: rules.ReplyAccumulator | None = None,
        final: Outcome | None = None,
    ) -> None:
        ok = outcome in ("complete", "abstained", "interrupted")
        logger.log(
            logging.INFO if ok else logging.WARNING,
            "chat_stream",
            extra={
                "request_id": request_id,
                "user_id": str(user.id),
                "conversation_id": str(conversation_id),
                "outcome": outcome,
                "saved": status,
                "finish_reason": final.finish_reason if final is not None else None,
                "has_source": final.has_source if final is not None else None,
                "error_code": final.error_code if final is not None else None,
                "frames": reply.frames if reply is not None else 0,
                "input_tokens": reply.usage.input_tokens if reply is not None else 0,
                "output_tokens": reply.usage.output_tokens if reply is not None else 0,
                "duration_ms": (time.monotonic_ns() - started) // 1_000_000,
            },
        )


async def _close(frames: object) -> None:
    """Cierra el generador del agente (y con él su conexión). Solo se llama bajo escudo o antes de empezar a enviar."""
    close = getattr(frames, "aclose", None)
    if close is not None:
        with anyio.CancelScope(shield=True):
            await close()
