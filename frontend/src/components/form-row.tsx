import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

export type Control = { id: string; "aria-invalid": true | undefined; "aria-describedby": string | undefined };

/** Etiqueta + control + ayuda + error, enlazados con `aria-describedby`. El id del control es `<idPrefix>-<name>`. */
export function FormRow({
  idPrefix,
  name,
  label,
  error,
  hint,
  children,
}: {
  idPrefix: string;
  name: string;
  label: string;
  error?: string | undefined;
  hint?: string | undefined;
  children: (control: Control) => ReactNode;
}) {
  const id = `${idPrefix}-${name}`;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id} className="text-[13px] font-semibold text-ink-soft">
        {label}
      </Label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy })}
      {hint ? (
        <p id={hintId} className="text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-[13px] font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
