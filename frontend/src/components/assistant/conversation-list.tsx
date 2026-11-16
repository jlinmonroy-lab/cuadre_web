import { Plus } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import type { ConversationSummary } from "@/lib/chat-api";
import { cn } from "@/lib/utils";

const WHEN = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" });

/** Las conversaciones de la persona, por última actividad. El título es texto plano (los primeros 60 caracteres de su primera pregunta). */
export function ConversationList({ conversations, currentId }: { conversations: ConversationSummary[]; currentId: string | null }) {
  return (
    <nav aria-label="Tus conversaciones" className="grid gap-3">
      <Link href="/asistente" className={cn(buttonVariants({ size: "sm" }), "w-full")}>
        <Plus aria-hidden="true" />
        Nueva conversación
      </Link>
      {conversations.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">Aún no has preguntado nada. Tus conversaciones aparecerán aquí.</p>
      ) : (
        <ul className="grid gap-1">
          {conversations.map((conversation) => {
            const current = conversation.id === currentId;
            return (
              <li key={conversation.id}>
                <Link
                  href={`/asistente?c=${conversation.id}`}
                  aria-current={current ? "true" : undefined}
                  className={cn(
                    "grid gap-0.5 rounded-md border px-3 py-2 text-sm hover:bg-action-soft focus-visible:ring-2 focus-visible:ring-ring",
                    current ? "border-action bg-action-soft" : "border-transparent",
                  )}
                >
                  <span className="font-semibold [overflow-wrap:anywhere]">{conversation.title}</span>
                  <span className="text-[13px] text-ink-soft">{WHEN.format(new Date(conversation.last_message_at))}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
