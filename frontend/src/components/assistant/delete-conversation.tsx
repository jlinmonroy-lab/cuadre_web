"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { deleteConversation } from "@/lib/chat-actions";

/** «Borrar conversación» en dos pasos y sin `confirm()` del navegador. Borra los mensajes y las valoraciones y no se puede deshacer. */
export function DeleteConversation({ conversationId }: { conversationId: string }) {
  const router = useRouter();
  const questionId = useId();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const cancel = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirming) cancel.current?.focus(); // por defecto, la opción segura
  }, [confirming]);

  if (!confirming) {
    return (
      <Button type="button" variant="outline" size="sm" onClick={() => setConfirming(true)}>
        <Trash2 aria-hidden="true" />
        Borrar conversación
      </Button>
    );
  }

  return (
    <div role="group" aria-labelledby={questionId} className="grid gap-2 rounded-md border border-status-error bg-status-error-bg px-3 py-2.5">
      <p id={questionId} className="text-sm font-semibold text-status-error">
        ¿Borrar esta conversación? Se borran sus mensajes y valoraciones y no se puede deshacer.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="destructive"
          size="sm"
          disabled={pending}
          onClick={() =>
            startTransition(async () => {
              setError(null);
              const result = await deleteConversation(conversationId);
              if (result.status === "error") {
                setError(result.message ?? "No se ha podido borrar.");
                return;
              }
              router.replace("/asistente");
            })
          }
        >
          {pending ? "Borrando…" : "Sí, borrar"}
        </Button>
        <Button ref={cancel} type="button" variant="outline" size="sm" disabled={pending} onClick={() => setConfirming(false)}>
          Cancelar
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
