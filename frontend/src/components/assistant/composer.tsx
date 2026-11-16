"use client";

import { Send, Square } from "lucide-react";
import type { RefObject } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { MAX_MESSAGE_CHARS, canSend, counterText } from "@/lib/chat";

/**
 * El campo para escribir y el botón de enviar (o «Detener» mientras llega la respuesta). Ctrl o ⌘ + Intro envía; Intro solo escribe un salto de línea.
 * El texto no se recorta al teclear: si pasa de 2.000 caracteres se dice cuántos sobran y el botón se desactiva.
 */
export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  busy,
  fieldRef,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  busy: boolean;
  fieldRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const over = value.trim().length > MAX_MESSAGE_CHARS;
  return (
    <form
      className="grid gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSend(value, busy)) onSend();
      }}
    >
      <Label htmlFor="asistente-mensaje">Tu pregunta</Label>
      <textarea
        id="asistente-mensaje"
        ref={fieldRef}
        value={value}
        rows={3}
        disabled={busy}
        aria-describedby="asistente-mensaje-ayuda"
        aria-invalid={over || undefined}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            if (canSend(value, busy)) onSend();
          }
        }}
        className="min-h-24 w-full resize-y rounded-md border border-rule-strong bg-white px-2.5 py-2 text-base focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p id="asistente-mensaje-ayuda" className={over ? "text-[13px] font-semibold text-status-error" : "text-[13px] text-ink-soft"}>
          {counterText(value)} · Ctrl o ⌘ + Intro para enviar
        </p>
        {busy ? (
          <Button type="button" variant="outline" onClick={onStop}>
            <Square aria-hidden="true" />
            Detener
          </Button>
        ) : (
          <Button type="submit" disabled={!canSend(value, busy)}>
            <Send aria-hidden="true" />
            Enviar
          </Button>
        )}
      </div>
    </form>
  );
}
