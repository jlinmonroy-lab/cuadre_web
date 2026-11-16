import type { Metadata } from "next";

import { Assistant } from "@/components/assistant/assistant";
import { ConversationList } from "@/components/assistant/conversation-list";
import { DeleteConversation } from "@/components/assistant/delete-conversation";
import { fromApi, isUuid } from "@/lib/chat";
import { getConversation, getConversations } from "@/lib/chat-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Asistente" };

export default async function AsistentePage(props: PageProps<"/asistente">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  // La conversación abierta vive en la dirección (`?c=`): es una lectura de servidor. Un valor que no es un uuid se trata como «ninguna».
  const requested = typeof params["c"] === "string" && isUuid(params["c"]) ? params["c"] : null;
  const conversations = await getConversations();
  const opened = requested ? await getConversation(requested) : null;
  const detail = opened?.status === "ok" ? opened.data : null;
  const missing = requested !== null && detail === null;

  return (
    <>
      <header className="mb-6">
        <h1>Asistente</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          Pregunta cómo funciona Cuadre o dudas fiscales generales: te respondo con fuentes oficiales o te digo cuándo conviene consultarlo con un profesional.
        </p>
      </header>
      <div className="grid gap-6 nav:grid-cols-[280px_minmax(0,1fr)] nav:items-start">
        <div className="grid gap-3">
          <div className="hidden nav:block">
            <ConversationList conversations={conversations} currentId={detail?.id ?? null} />
          </div>
          <details className="rounded-panel border border-rule bg-sheet nav:hidden">
            <summary className="cursor-pointer px-4 py-3 font-semibold">Conversaciones ({conversations.length})</summary>
            <div className="px-4 pb-4">
              <ConversationList conversations={conversations} currentId={detail?.id ?? null} />
            </div>
          </details>
        </div>
        <div className="grid min-w-0 gap-4">
          {missing ? (
            <p role="status" className="rounded-md border border-status-doubt-line bg-status-doubt-bg px-3 py-2 text-status-doubt">
              No encontramos esa conversación. Puedes empezar una nueva o abrir otra de la lista.
            </p>
          ) : null}
          {detail ? (
            <div className="flex flex-wrap items-start justify-between gap-3">
              <h2 className="min-w-0 text-lg [overflow-wrap:anywhere]">{detail.title}</h2>
              <DeleteConversation conversationId={detail.id} />
            </div>
          ) : null}
          <Assistant key={detail?.id ?? "nueva"} conversationId={detail?.id ?? null} initialMessages={detail ? detail.messages.map(fromApi) : []} />
        </div>
      </div>
    </>
  );
}
