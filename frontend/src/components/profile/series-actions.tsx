"use client";

import { useActionState, useState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { initialFormState, type FormState } from "@/lib/form-state";
import { createSeries, setDefaultSeries, setSeriesArchived, updateSeries } from "@/lib/profile-actions";

export type SeriesRow = {
  id: string;
  code: string;
  description: string | null;
  first_number: number;
  next_number: number;
  is_default: boolean;
  archived: boolean;
  in_use: boolean;
};

const FIELD_IDS = (prefix: string) => ({ code: `${prefix}-code`, description: `${prefix}-description`, first_number: `${prefix}-first_number` });

function Feedback({ state }: { state: FormState }) {
  return (
    <p aria-live="polite" className={`text-[13px] font-semibold ${state.status === "error" ? "text-status-error" : "text-status-ok"}`}>
      {state.status === "idle" ? "" : (state.message ?? "")}
    </p>
  );
}

/** Editar una serie. Con facturas emitidas, el código y el número inicial no se pueden cambiar (la base lo impide): se enseñan desactivados. */
function SeriesEditor({ series, view, onClose }: { series: SeriesRow; view: string; onClose: () => void }) {
  const [state, action, pending] = useActionState(updateSeries.bind(null, series.id), initialFormState);
  const prefix = `serie-${view}-${series.id}`;
  const errors = state.fieldErrors ?? {};
  const values = state.values ?? { code: series.code, description: series.description ?? "", first_number: String(series.first_number) };
  const lockedHint = series.in_use ? "Esta serie ya tiene facturas emitidas: no se puede cambiar." : undefined;
  return (
    <form action={action} noValidate className="grid gap-3 rounded-md border border-rule bg-white p-3">
      <ErrorSummary state={state} fieldIds={FIELD_IDS(prefix)} />
      <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(200px,1fr))]">
        <FormRow idPrefix={prefix} name="code" label="Código" error={errors["code"]} hint={lockedHint}>
          {(control) => <Input {...control} name="code" maxLength={8} autoComplete="off" disabled={series.in_use} defaultValue={values["code"] ?? ""} />}
        </FormRow>
        <FormRow idPrefix={prefix} name="description" label="Descripción" error={errors["description"]}>
          {(control) => <Input {...control} name="description" maxLength={80} autoComplete="off" defaultValue={values["description"] ?? ""} />}
        </FormRow>
        <FormRow idPrefix={prefix} name="first_number" label="Número inicial" error={errors["first_number"]} hint={lockedHint}>
          {(control) => (
            <Input {...control} name="first_number" inputMode="numeric" autoComplete="off" disabled={series.in_use} className="text-right tabular-nums" defaultValue={values["first_number"] ?? ""} />
          )}
        </FormRow>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Guardando…" : "Guardar serie"}
        </Button>
        <Button type="button" variant="outline" onClick={onClose}>
          Cerrar
        </Button>
        <Feedback state={state} />
      </div>
    </form>
  );
}

/** Las acciones de una serie: «Hacer predeterminada», «Editar» y «Archivar» / «Reactivar». El servidor decide cuáles valen. */
export function SeriesActions({ series, view }: { series: SeriesRow; view: "tarjeta" | "tabla" }) {
  const [editing, setEditing] = useState(false);
  // Un único estado para las dos acciones: el mensaje que se enseña es siempre el de la ÚLTIMA (con dos `useActionState` separados, el éxito
  // de «Hacer predeterminada» tapaba el error posterior de «Archivar»).
  const [state, action, pending] = useActionState(
    async (_previous: FormState, formData: FormData): Promise<FormState> =>
      formData.get("op") === "default" ? setDefaultSeries(series.id) : setSeriesArchived(series.id, !series.archived),
    initialFormState,
  );
  const name = `serie ${series.code}`;
  return (
    <div className="grid gap-2">
      <form action={action} className="flex flex-wrap gap-2">
        {!series.is_default && !series.archived ? (
          <Button type="submit" name="op" value="default" variant="outline" size="sm" disabled={pending} aria-label={`Hacer predeterminada la ${name}`}>
            Hacer predeterminada
          </Button>
        ) : null}
        <Button type="button" variant="outline" size="sm" aria-expanded={editing} aria-label={`Editar la ${name}`} onClick={() => setEditing((open) => !open)}>
          Editar
        </Button>
        <Button type="submit" name="op" value="archive" variant="outline" size="sm" disabled={pending} aria-label={`${series.archived ? "Reactivar" : "Archivar"} la ${name}`}>
          {series.archived ? "Reactivar" : "Archivar"}
        </Button>
      </form>
      <Feedback state={state} />
      {editing ? <SeriesEditor series={series} view={view} onClose={() => setEditing(false)} /> : null}
    </div>
  );
}

/** «Añadir serie»: un desplegable nativo (accesible con teclado) con el formulario. */
export function AddSeries() {
  const [state, action, pending] = useActionState(createSeries, initialFormState);
  const errors = state.fieldErrors ?? {};
  const values = state.values ?? {};
  const prefix = "serie-nueva";
  return (
    <details className="rounded-panel border border-rule bg-sheet p-4" open={state.status === "error" ? true : undefined}>
      <summary className="cursor-pointer text-[15px] font-semibold text-action hover:text-action-hover">Añadir serie</summary>
      <form action={action} noValidate className="mt-4 grid max-w-3xl gap-4">
        <ErrorSummary state={state} fieldIds={FIELD_IDS(prefix)} />
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(220px,1fr))]">
          <FormRow idPrefix={prefix} name="code" label="Código" error={errors["code"]} hint="De 1 a 8 letras, números o guiones.">
            {(control) => <Input {...control} name="code" maxLength={8} autoComplete="off" autoCapitalize="characters" defaultValue={values["code"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={prefix} name="description" label="Descripción" error={errors["description"]}>
            {(control) => <Input {...control} name="description" maxLength={80} autoComplete="off" defaultValue={values["description"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={prefix} name="first_number" label="Número inicial" error={errors["first_number"]} hint="Si lo dejas vacío empieza en 1.">
            {(control) => <Input {...control} name="first_number" inputMode="numeric" autoComplete="off" className="text-right tabular-nums" defaultValue={values["first_number"] ?? ""} />}
          </FormRow>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="make_default" className="size-4 accent-[var(--color-action)]" />
          Usarla como serie predeterminada
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? "Añadiendo…" : "Añadir serie"}
          </Button>
          <Feedback state={state} />
        </div>
      </form>
    </details>
  );
}
