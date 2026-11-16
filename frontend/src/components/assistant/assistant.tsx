"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Composer } from "@/components/assistant/composer";
import { MessageView } from "@/components/assistant/message-view";
import { Notice } from "@/components/assistant/notice";
import { Button } from "@/components/ui/button";
import {
  CONNECTION_LOST,
  EMPTY_THREAD,
  SESSION_EXPIRED,
  applyEvent,
  canSend,
  fromReply,
  interrupted,
  isUuid,
  readChatStream,
  startReply,
  userMessage,
  type ChatEvent,
  type LiveReply,
  type ThreadMessage,
} from "@/lib/chat";

type Failure = { code: string; message: string };

/**
 * Tras la primera respuesta de una conversación nueva la dirección pasa a `?c=<id>` y la pantalla se vuelve a montar (cambia la `key` de la página): el
 * foco que se le dio al campo se pierde con la instancia vieja. Esta marca se lo pasa a la nueva. Es de módulo a propósito: no sobrevive a una carga
 * completa de la página, que es lo que se quiere.
 */
let focusFieldOnMount = false;

/** Lo que devuelve el Route Handler cuando falla ANTES del primer frame (`{code, message, conversation_id?}`); cualquier otra cosa es «no es de fiar». */
async function problemOf(response: Response): Promise<{ failure: Failure; conversationId: string | null }> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null) {
      const { code, message, conversation_id: conversationId } = body as Record<string, unknown>;
      if (typeof code === "string" && typeof message === "string" && message.length <= 300) {
        return { failure: { code, message }, conversationId: isUuid(conversationId) ? conversationId : null };
      }
    }
  } catch {
    // Se ignora: cae en el mensaje genérico.
  }
  return { failure: { code: "error", message: "No hemos podido enviar tu pregunta. Inténtalo de nuevo." }, conversationId: null };
}

/**
 * El hilo y el campo para escribir. El envío va por `POST /asistente/enviar` (un Route Handler que reenvía el flujo de la API sin acumularlo); el
 * navegador nunca ve el JWT. El texto llega token a token y se pinta como texto plano. «Detener» corta la lectura: lo recibido se queda, marcado como
 * interrumpido, y el servidor guarda lo mismo. La respuesta no se anuncia token a token (sería ruido para un lector de pantalla): una región
 * `role="status"` dice solo «escribiendo» y «lista».
 */
export function Assistant({ conversationId, initialMessages }: { conversationId: string | null; initialMessages: ThreadMessage[] }) {
  const router = useRouter();
  const [conversation, setConversation] = useState<string | null>(conversationId);
  const [messages, setMessages] = useState<ThreadMessage[]>(initialMessages);
  const [live, setLive] = useState<LiveReply | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [announce, setAnnounce] = useState("");
  const [lastSent, setLastSent] = useState<string | null>(null); // para «Reintentar»
  const abort = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const field = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const refocus = useRef(false);

  // El campo está desactivado mientras llega la respuesta, y un elemento desactivado no admite el foco: se le da cuando ya vuelve a estar activo.
  useEffect(() => {
    if (!busy && refocus.current) {
      refocus.current = false;
      field.current?.focus();
    }
  }, [busy]);

  useEffect(() => {
    if (focusFieldOnMount) {
      focusFieldOnMount = false;
      field.current?.focus();
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      abort.current?.abort(); // al irse de la pantalla se corta la lectura: la API guarda lo recibido como interrumpido
    };
  }, []);

  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false; // al abrir una conversación no se desplaza la página
      return;
    }
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, live?.text.length]);

  async function send(raw: string, retry: boolean) {
    const content = raw.trim();
    if (!canSend(content, busy)) return;
    const controller = new AbortController();
    abort.current = controller;
    setLastSent(content);
    const localId = `local-${crypto.randomUUID()}`;
    setBusy(true);
    setFailure(null);
    setAnnounce("El asistente está escribiendo…");
    if (!retry) {
      setMessages((current) => [...current, userMessage(localId, content, false)]);
      setDraft("");
    }

    let reply: LiveReply = startReply();
    setLive(reply);
    let target = conversation;
    let streamed = false;
    try {
      const response = await fetch("/asistente/enviar", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ conversation_id: target, content }),
        signal: controller.signal,
      });
      const type = response.headers.get("content-type") ?? "";
      if (response.redirected || !(type.startsWith("text/event-stream") || type.startsWith("application/json"))) {
        // El proxy de sesión contestó con una redirección a /login (HTML): la sesión caducó.
        setFailure({ code: "session", message: SESSION_EXPIRED });
        setLive(null);
        return;
      }
      if (!type.startsWith("text/event-stream") || response.body === null) {
        const problem = await problemOf(response);
        setFailure(problem.failure);
        setLive(null);
        if (problem.conversationId !== null) {
          // El mensaje se guardó pero el asistente no respondió: se sigue en esa conversación para poder reintentar.
          target = problem.conversationId;
          setConversation(target);
          router.refresh();
        }
        return;
      }
      const outcome = await readChatStream(
        response.body,
        (event: ChatEvent) => {
          if (event.event === "start") {
            streamed = true;
            target = event.data.conversation_id;
            setConversation(target);
            setMessages((current) => current.map((m) => (m.id === localId ? { ...m, id: event.data.user_message_id, saved: true } : m)));
          }
          reply = applyEvent(reply, event);
          setLive(reply);
        },
        controller.signal,
      );
      if (outcome === "closed") {
        reply = interrupted(reply);
        setFailure({ code: "interrupted", message: CONNECTION_LOST });
      }
    } catch (error) {
      reply = interrupted(reply);
      const stopped = error instanceof DOMException && error.name === "AbortError";
      if (!stopped && mounted.current) setFailure({ code: "interrupted", message: CONNECTION_LOST });
    } finally {
      if (mounted.current) {
        if (streamed) {
          setMessages((current) => [...current, fromReply(reply, `local-${crypto.randomUUID()}`)]);
          setAnnounce(reply.terminal === "done" ? "Respuesta lista." : "");
        } else {
          setAnnounce("");
        }
        setLive(null);
        setBusy(false);
        refocus.current = true;
        if (streamed) {
          if (conversationId === null && target !== null) {
            focusFieldOnMount = true;
            router.replace(`/asistente?c=${target}`);
          } else router.refresh();
        }
      }
    }
  }

  return (
    <div className="grid min-w-0 gap-4">
      <section aria-label="Conversación con el asistente" aria-busy={busy} className="grid gap-3">
        {messages.length === 0 && live === null ? (
          <p className="rounded-panel border border-rule bg-sheet p-6 text-center text-ink-soft">{EMPTY_THREAD}</p>
        ) : (
          <ol className="m-0 grid list-none gap-3 p-0">
            {messages.map((message) => (
              <MessageView key={message.id} message={message} />
            ))}
            {live ? <MessageView message={fromReply(live, "en-curso")} pending tool={live.tool} /> : null}
          </ol>
        )}
        <div ref={end} />
      </section>

      {failure ? (
        <div role="alert" className="grid gap-2 rounded-md border border-status-error bg-status-error-bg px-3 py-2.5 text-status-error">
          <p className="text-sm font-semibold">{failure.message}</p>
          {failure.code !== "session" && lastSent !== null && !busy && failure.code !== "interrupted" ? (
            <div>
              <Button type="button" size="sm" variant="outline" onClick={() => void send(lastSent, true)}>
                Reintentar
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      <Composer
        value={draft}
        onChange={setDraft}
        onSend={() => void send(draft, false)}
        onStop={() => abort.current?.abort()}
        busy={busy}
        fieldRef={field}
      />
      <Notice />
      <p role="status" className="sr-only">
        {announce}
      </p>
    </div>
  );
}
