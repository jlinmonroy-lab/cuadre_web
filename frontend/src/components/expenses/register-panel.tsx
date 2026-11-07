"use client";

import { CircleCheck, CircleX, TriangleAlert } from "lucide-react";
import { useActionState, useState } from "react";

import { useDirty } from "@/components/expenses/dirty-context";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { confirmDocument } from "@/lib/expenses-actions";
import {
  CATEGORY_LABELS,
  EXPENSE_CATEGORIES,
  checkView,
  registerGate,
  type ExpenseCategory,
  type Validation,
} from "@/lib/expenses";
import { initialFormState } from "@/lib/form-state";

/**
 * Las comprobaciones del servidor sobre lo GUARDADO y el botón «Registrar gasto» (SPEC-W-003 §5.5). La interfaz no valida nada fiscal:
 * enseña lo que devuelve la API y `registerGate` decide solo cuándo se puede pulsar (nada sin guardar, todo en verde y, si hay sospecha de
 * instrucciones ocultas, la casilla marcada). El servidor y la base lo vuelven a decidir.
 */
export function RegisterPanel({ documentId, validation }: { documentId: string; validation: Validation | null }) {
  const { dirty } = useDirty();
  const [state, action, pending] = useActionState(confirmDocument.bind(null, documentId), initialFormState);
  const [chosen, setChosen] = useState<ExpenseCategory | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);

  const suggested = validation?.preview.suggested_category ?? null;
  const category = chosen ?? suggested ?? "other"; // lo que elige la persona gana a la sugerencia, aunque esta cambie al corregir
  const gate = registerGate({ validation, dirty, acknowledged, pending });

  return (
    <section aria-labelledby="comprobaciones-titulo" className="grid gap-4 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
      <h2 id="comprobaciones-titulo">Comprobaciones</h2>

      <div aria-live="polite" className="grid gap-4">
        {validation ? (
          <div className={dirty ? "grid gap-4 opacity-60" : "grid gap-4"}>
            {dirty ? <p className="text-[13px] text-ink-soft">Comprobado con lo último que guardaste.</p> : null}
            <ul className="grid gap-2.5 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
              {validation.checks.map((check) => {
                const view = checkView(check);
                return (
                  <li key={check.code} className="flex items-start gap-2 text-sm">
                    {view.ok ? (
                      <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-status-ok" />
                    ) : (
                      <CircleX aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-status-error" />
                    )}
                    <span>
                      <span className="sr-only">{view.statusText}: </span>
                      {view.label}
                      {view.ok ? null : (
                        <>
                          : <strong>revisar</strong>
                        </>
                      )}
                      {/* El motivo viene de la API: se pinta como texto. */}
                      {view.detail ? <span className="mt-0.5 block text-[13px] text-status-error">{view.detail}</span> : null}
                    </span>
                  </li>
                );
              })}
            </ul>

            {validation.warnings.length > 0 ? (
              <ul className="grid gap-1.5">
                {validation.warnings.map((warning) => (
                  <li key={warning.code} className="flex items-start gap-2 rounded-md border border-status-doubt-line bg-status-doubt-bg px-3 py-2 text-sm text-status-doubt">
                    <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                    <span>{warning.message}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            <p className="text-sm">
              <strong>Se deducirá el IVA: {validation.preview.deductible_vat ? "sí" : "no"}.</strong>
              {validation.preview.deductible_note ? <> {validation.preview.deductible_note}</> : null}
            </p>
          </div>
        ) : (
          <p className="text-sm text-ink-soft">Todavía no hay datos guardados que comprobar. Rellena el formulario y pulsa «Guardar cambios».</p>
        )}
      </div>

      <form action={action} className="grid gap-4 border-t border-rule pt-4">
        <div className="grid max-w-sm gap-1.5">
          <Label htmlFor="registrar-categoria" className="text-[13px] font-semibold text-ink-soft">
            Categoría
          </Label>
          <NativeSelect id="registrar-categoria" name="category" value={category} onChange={(event) => setChosen(event.target.value as ExpenseCategory)}>
            {EXPENSE_CATEGORIES.map((option) => (
              <option key={option} value={option}>
                {CATEGORY_LABELS[option]}
                {option === suggested ? " · sugerida" : ""}
              </option>
            ))}
          </NativeSelect>
          {suggested ? <p className="text-xs text-ink-soft">La sugerida sale del nombre del proveedor; puedes elegir otra.</p> : null}
        </div>

        {validation?.requires_acknowledgement ? (
          <div className="grid gap-1 rounded-md border border-status-doubt-line bg-status-doubt-bg px-3 py-3 text-status-doubt">
            <label className="flex items-start gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                name="acknowledge_suspicion"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
                className="mt-0.5 size-4 accent-[var(--color-action)]"
              />
              <span>He comparado los datos con el original.</span>
            </label>
            <p className="text-xs">El documento contiene texto que parece una instrucción dirigida a un sistema automático: compruébalo antes de registrar.</p>
          </div>
        ) : null}

        {state.status === "error" ? (
          <p role="alert" className="rounded-md border border-status-error bg-status-error-bg px-3 py-2.5 text-sm font-semibold text-status-error">
            {state.message}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button type="submit" disabled={!gate.enabled} aria-describedby={gate.reason ? "registrar-motivo" : undefined}>
            {pending ? "Registrando…" : "Registrar gasto"}
          </Button>
          {gate.reason ? (
            <p id="registrar-motivo" className="text-sm font-semibold text-ink-soft">
              {gate.reason}
            </p>
          ) : null}
        </div>
      </form>
    </section>
  );
}
