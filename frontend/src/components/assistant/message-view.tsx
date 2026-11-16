import { LoaderCircle } from "lucide-react";

import { Feedback } from "@/components/assistant/feedback";
import { Notice } from "@/components/assistant/notice";
import { formatValidAsOf, linkHref, noteFor, referralLine, type Citation, type ThreadMessage } from "@/lib/chat";
import { cn } from "@/lib/utils";

function Source({ citation }: { citation: Citation }) {
  const href = linkHref(citation.url);
  const valid = formatValidAsOf(citation.valid_as_of);
  return (
    <li className="text-sm">
      <span className="font-semibold">{citation.publisher}</span>
      {" · "}
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-action underline underline-offset-2 hover:text-action-hover [overflow-wrap:anywhere]">
          {citation.title}
        </a>
      ) : (
        <span className="[overflow-wrap:anywhere]">{citation.title}</span>
      )}
      {valid ? <span className="text-ink-soft">{` · vigente a ${valid}`}</span> : null}
      {citation.quote ? <q className="mt-0.5 block text-ink-soft [overflow-wrap:anywhere]">{citation.quote}</q> : null}
    </li>
  );
}

/**
 * Un mensaje del hilo. TODO el texto (el de la persona, el del asistente, el de las citas) se pinta como texto plano: React lo escapa y no hay
 * `dangerouslySetInnerHTML` ni Markdown (D-10). Una cita solo es un enlace si su URL es `https`.
 */
export function MessageView({ message, pending = false, tool = null }: { message: ThreadMessage; pending?: boolean; tool?: string | null }) {
  const mine = message.role === "user";
  const note = noteFor(message);
  const refer = message.abstention ? referralLine(message.abstention.referral) : null;
  return (
    <li className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <article
        aria-label={mine ? "Tú" : "Asistente"}
        className={cn("min-w-0 max-w-[min(100%,46rem)] rounded-panel border px-4 py-3", mine ? "border-transparent bg-action-soft" : "border-rule bg-sheet")}
      >
        {message.content ? <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{message.content}</p> : null}
        {pending && !message.content ? (
          <p className="flex items-center gap-2 text-ink-soft">
            <LoaderCircle aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />
            Preparando la respuesta…
          </p>
        ) : null}
        {pending && tool ? (
          <p className="mt-2 flex items-center gap-2 text-sm text-ink-soft">
            <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin motion-reduce:animate-none" />
            Consultando tus datos…
          </p>
        ) : null}
        {message.citations.length > 0 ? (
          <div className="mt-3 grid gap-1 border-t border-rule pt-3">
            <h3 className="text-[13px] font-semibold text-ink-soft">Fuentes</h3>
            <ul className="grid gap-1.5">
              {message.citations.map((citation) => (
                <Source key={citation.id} citation={citation} />
              ))}
            </ul>
          </div>
        ) : null}
        {message.abstention ? (
          <div className="mt-3 grid gap-2 rounded-md border border-status-doubt-line bg-status-doubt-bg px-3 py-2 text-sm text-status-doubt">
            {refer ? <p className="font-semibold">{refer}</p> : null}
            <Notice className="bg-transparent px-0 py-0" />
          </div>
        ) : null}
        {note ? (
          <p
            role={note.kind === "error" || note.kind === "interrupted" ? "alert" : undefined}
            className={cn(
              "mt-3 rounded-md border px-3 py-2 text-sm",
              note.kind === "error" ? "border-status-error bg-status-error-bg font-semibold text-status-error" : "border-status-doubt-line bg-status-doubt-bg text-status-doubt",
            )}
          >
            {note.text}
          </p>
        ) : null}
        {!mine && !pending && message.saved ? <Feedback messageId={message.id} initialRating={message.rating} initialReason={message.reason} /> : null}
      </article>
    </li>
  );
}
