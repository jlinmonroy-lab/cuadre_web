"use client";

import { useEffect, useRef } from "react";

import type { FormState } from "@/lib/form-state";

/** Resumen de errores del formulario (`role="alert"`). Recibe el foco al enviar con errores y enlaza cada error con su campo. */
export function ErrorSummary({ state, fieldIds }: { state: FormState; fieldIds: Record<string, string> }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (state.status === "error") ref.current?.focus();
  }, [state]);

  if (state.status !== "error") return null;
  const entries = Object.entries(state.fieldErrors ?? {}).filter(([field, message]) => message && fieldIds[field]);

  return (
    <div
      ref={ref}
      role="alert"
      tabIndex={-1}
      className="grid gap-1.5 rounded-md border border-status-error bg-status-error-bg px-3 py-2.5 text-sm text-status-error outline-none focus-visible:ring-2 focus-visible:ring-status-error"
    >
      {state.message ? <p className="font-semibold">{state.message}</p> : <p className="font-semibold">Revisa estos datos:</p>}
      {entries.length > 0 ? (
        <ul className="list-disc pl-5">
          {entries.map(([field, message]) => (
            <li key={field}>
              <a href={`#${fieldIds[field]}`} className="underline underline-offset-2">
                {message}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
