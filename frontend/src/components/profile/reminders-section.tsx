"use client";

import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { initialFormState } from "@/lib/form-state";
import { saveReminders } from "@/lib/reminders-actions";

const PREFIX = "recordatorios";
const FIELD_IDS = { lead_days: `${PREFIX}-lead_days` };

/**
 * Recordatorios por correo antes de cada plazo trimestral (RF-015). La interfaz muestra lo que dice el servidor y no decide el rango: los días
 * (de 1 a 30) los valida la API, que devuelve su texto, y aparece junto al campo. Tiene su propio botón: es una escritura distinta de la del perfil.
 */
export function RemindersSection({ initial }: { initial: { enabled: boolean; lead_days: number } }) {
  const [state, action, pending] = useActionState(saveReminders, initialFormState);
  const enabled = state.values ? state.values["enabled"] === "on" : initial.enabled;
  const leadDays = state.values?.["lead_days"] ?? String(initial.lead_days);
  const errors = state.fieldErrors ?? {};
  const saved = state.status === "sent";
  // `key`: al terminar la acción React reinicia el formulario a sus valores iniciales; remontar los controles conserva lo guardado (o lo tecleado).
  const remount = `${enabled}-${leadDays}`;

  return (
    <section aria-labelledby="recordatorios-titulo" className="grid gap-4 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
      <h2 id="recordatorios-titulo">Recordatorios</h2>
      <p className="max-w-[70ch] text-[13px] text-ink-soft">
        Te escribimos antes de cada plazo trimestral con la fecha límite, el importe estimado del 303 y del 130 y las facturas pendientes de revisar.
        Los importes son orientativos y la aplicación no presenta nada ante la AEAT.
      </p>
      <form action={action} noValidate className="grid max-w-xl gap-4">
        <ErrorSummary state={state} fieldIds={FIELD_IDS} />
        <div className="flex items-center gap-2.5">
          <input
            key={`c-${remount}`}
            id={`${PREFIX}-enabled`}
            name="enabled"
            type="checkbox"
            defaultChecked={enabled}
            className="size-4 accent-action"
          />
          <Label htmlFor={`${PREFIX}-enabled`} className="text-[15px] font-semibold">
            Avisarme por correo antes de cada plazo
          </Label>
        </div>
        <FormRow
          idPrefix={PREFIX}
          name="lead_days"
          label="Días de antelación"
          error={errors["lead_days"]}
          hint="Entre 1 y 30. Por ejemplo, con 10 días te avisamos el 20 de enero para el plazo del 30."
        >
          {(control) => (
            <Input
              key={`n-${remount}`}
              {...control}
              name="lead_days"
              inputMode="numeric"
              autoComplete="off"
              className="max-w-32 text-right tabular-nums"
              defaultValue={leadDays}
            />
          )}
        </FormRow>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? "Guardando…" : "Guardar recordatorios"}
          </Button>
          <p aria-live="polite" className="text-sm font-semibold text-status-ok">
            {saved ? (state.message ?? "Recordatorios guardados.") : ""}
          </p>
        </div>
      </form>
    </section>
  );
}
