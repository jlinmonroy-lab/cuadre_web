"use client";

import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { initialFormState } from "@/lib/form-state";
import { issueRectification } from "@/lib/invoices-actions";
import type { InvoiceFormState } from "@/lib/invoices-form";

const fieldIds = (prefix: string): Record<string, string> => ({
  reason: `${prefix}-reason`,
  corrected_base: `${prefix}-corrected_base`,
  issue_date: `${prefix}-issue_date`,
});

/**
 * «Emitir rectificativa»: una factura emitida no se edita; se corrige con otra que lleva la diferencia. La persona escribe la base CORRECTA (o
 * anula la factura por completo) y el servidor calcula la diferencia con lo vigente. Con éxito, lleva a la rectificativa nueva.
 */
export function RectifyForm({ invoiceId, displayNumber, standingLabel, today }: { invoiceId: string; displayNumber: string; standingLabel: string; today: string }) {
  const [state, action, pending] = useActionState<InvoiceFormState, FormData>(issueRectification.bind(null, invoiceId), initialFormState);
  const prefix = `rectificar-${invoiceId}`;
  const values = state.values ?? {};
  const errors = state.fieldErrors ?? {};
  return (
    // Abierto mientras haya un error que leer: si pasara de `true` a `undefined` React quitaría el atributo y se cerraría escondiéndolo.
    <details className="rounded-panel border border-rule bg-sheet p-4" open={state.status === "idle" ? undefined : true}>
      <summary className="cursor-pointer text-[15px] font-semibold text-action hover:text-action-hover">Emitir rectificativa</summary>
      <form action={action} noValidate className="mt-4 grid max-w-3xl gap-4">
        <p className="text-sm text-ink-soft">
          Rectifica la factura {displayNumber}. Escribe cómo debería haber quedado y la aplicación emite una rectificativa con la diferencia; la factura original no se
          toca.
        </p>
        <ErrorSummary state={state} fieldIds={fieldIds(prefix)} />
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(240px,1fr))]">
          <div className="[grid-column:1/-1]">
            <FormRow idPrefix={prefix} name="reason" label="Motivo de la rectificación" error={errors["reason"]}>
              {(control) => <Input {...control} name="reason" autoComplete="off" maxLength={300} defaultValue={values["reason"] ?? ""} />}
            </FormRow>
          </div>
          <FormRow
            idPrefix={prefix}
            name="corrected_base"
            label="Base corregida (€)"
            error={errors["corrected_base"]}
            hint={`Base vigente: ${standingLabel}. Si marcas «Anular por completo», se ignora.`}
          >
            {(control) => <Input {...control} name="corrected_base" inputMode="decimal" autoComplete="off" placeholder="800,00" defaultValue={values["corrected_base"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={prefix} name="issue_date" label="Fecha de la rectificativa" error={errors["issue_date"]}>
            {(control) => <Input {...control} name="issue_date" type="date" max={today} defaultValue={values["issue_date"] ?? today} />}
          </FormRow>
        </div>
        <div className="flex items-center gap-2">
          {/* `key`: tras un error el formulario se reinicia a sus valores iniciales; sin remontar la casilla se perdería lo marcado. */}
          <input
            key={values["annul"] ?? ""}
            id={`${prefix}-annul`}
            name="annul"
            type="checkbox"
            defaultChecked={values["annul"] === "on"}
            className="size-4 accent-[var(--color-action)]"
          />
          <Label htmlFor={`${prefix}-annul`} className="text-[15px]">
            Anular por completo (la base corregida será 0,00 €)
          </Label>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button type="submit" disabled={pending}>
            {pending ? "Emitiendo…" : "Emitir rectificativa"}
          </Button>
          <p className="text-[13px] text-ink-soft" aria-live="polite">
            {pending ? "Estamos emitiendo la rectificativa y preparando su PDF; puede tardar unos segundos." : "Recibe su propio número y ya no se puede modificar."}
          </p>
        </div>
      </form>
    </details>
  );
}
