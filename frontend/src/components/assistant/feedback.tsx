"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useId, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { REASONS, type FeedbackReason, type Rating } from "@/lib/chat";
import { rateMessage } from "@/lib/chat-actions";

/**
 * La valoración de una respuesta (RF-018, D-04): «útil» o «no útil», y «no útil» pide un motivo de una lista cerrada (sin texto libre: podría ser un dato
 * personal). Se puede cambiar. Es local: no se envía al agente.
 */
export function Feedback({ messageId, initialRating, initialReason }: { messageId: string; initialRating: Rating | null; initialReason: FeedbackReason | null }) {
  const groupId = useId();
  const [rating, setRating] = useState<Rating | null>(initialRating);
  const [reason, setReason] = useState<FeedbackReason | null>(initialReason);
  const [choosing, setChoosing] = useState(false);
  const [draft, setDraft] = useState<FeedbackReason | null>(initialReason);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, startTransition] = useTransition();

  function save(next: Rating, why: FeedbackReason | null) {
    startTransition(async () => {
      setError(null);
      setSaved(false);
      const result = await rateMessage(messageId, next, why);
      if (result.status === "error") {
        setError(result.message ?? "No se ha podido guardar la valoración.");
        return;
      }
      setRating(next);
      setReason(why);
      setChoosing(false);
      setSaved(true);
    });
  }

  return (
    <div className="mt-3 grid gap-2 border-t border-rule pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold text-ink-soft" id={`${groupId}-label`}>
          ¿Te ha servido?
        </span>
        <div role="group" aria-labelledby={`${groupId}-label`} className="flex gap-2">
          <Button type="button" size="sm" variant="outline" aria-pressed={rating === "up"} disabled={pending} onClick={() => save("up", null)} className="aria-pressed:border-action aria-pressed:bg-action-soft">
            <ThumbsUp aria-hidden="true" />
            Útil
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-pressed={rating === "down"}
            aria-expanded={choosing}
            disabled={pending}
            onClick={() => {
              setDraft(reason);
              setChoosing(true);
            }}
            className="aria-pressed:border-action aria-pressed:bg-action-soft"
          >
            <ThumbsDown aria-hidden="true" />
            No útil
          </Button>
        </div>
        {saved && !choosing ? (
          <span role="status" className="text-[13px] text-status-ok">
            Valoración guardada.
          </span>
        ) : null}
      </div>
      {choosing ? (
        <fieldset className="grid gap-1.5 rounded-md border border-rule bg-paper px-3 py-2.5">
          <legend className="px-1 text-[13px] font-semibold text-ink-soft">¿Qué ha fallado?</legend>
          {REASONS.map((option) => (
            <label key={option.value} className="flex items-center gap-2 text-sm">
              <input type="radio" name={`${groupId}-reason`} value={option.value} checked={draft === option.value} onChange={() => setDraft(option.value)} className="size-4 accent-action" />
              {option.label}
            </label>
          ))}
          <div className="mt-1 flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={pending || draft === null} onClick={() => draft !== null && save("down", draft)}>
              {pending ? "Guardando…" : "Guardar valoración"}
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => setChoosing(false)}>
              Cancelar
            </Button>
          </div>
        </fieldset>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
