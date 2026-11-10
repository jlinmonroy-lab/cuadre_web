"use client";

import { useActionState, useState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { CLIENT_FORM_FIELDS } from "@/lib/clients-form";
import { createClient } from "@/lib/clients-actions";
import { useCountries } from "@/components/clients/countries-context";
import { CLIENT_KINDS, taxIdLabel, type ClientKind } from "@/lib/countries";
import { initialFormState, type FormState } from "@/lib/form-state";

/** Los ids de los campos de un formulario (el del resumen de errores enlaza a ellos). */
export const clientFieldIds = (prefix: string): Record<string, string> => Object.fromEntries(CLIENT_FORM_FIELDS.map((name) => [name, `${prefix}-${name}`]));

/** Lo que se ve en un cliente nuevo: una empresa en España (lo más habitual); la persona lo cambia con los selectores. */
const NEW_CLIENT: Record<string, string> = { kind: "business", country: "ES" };

export function Feedback({ state }: { state: FormState }) {
  return (
    <p aria-live="polite" className={`text-[13px] font-semibold ${state.status === "error" ? "text-status-error" : "text-status-ok"}`}>
      {state.status === "idle" ? "" : (state.message ?? "")}
    </p>
  );
}

/**
 * Los cinco campos de la ficha. El rótulo y la ayuda del identificador siguen al país y al tipo que la persona va eligiendo (NIF, NIF-IVA o
 * identificador fiscal): es solo presentación, el control lo hace el servidor y el ámbito lo calcula él. `source` es lo que identifica cada
 * resultado de la acción: cuando cambia (se guardó, o hubo errores y vuelven los valores tecleados), el país y el tipo se resincronizan.
 */
export function ClientFields({ prefix, values, errors, source }: { prefix: string; values: Record<string, string>; errors: Record<string, string | undefined>; source: unknown }) {
  const { countries } = useCountries(); // nombres del servidor: ver `countries-context.tsx`
  const [picked, setPicked] = useState({ source, country: values["country"] ?? "", kind: values["kind"] ?? "business" });
  let current = picked;
  if (picked.source !== source) {
    // Ajuste de estado al cambiar la entrada (patrón de React): sin un efecto ni un segundo pintado con el rótulo viejo.
    current = { source, country: values["country"] ?? "", kind: values["kind"] ?? "business" };
    setPicked(current);
  }
  const kind: ClientKind = current.kind === "individual" ? "individual" : "business";
  const identifier = taxIdLabel(current.country, kind);

  return (
    <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(240px,1fr))]">
      <FormRow idPrefix={prefix} name="name" label="Nombre o razón social" error={errors["name"]}>
        {(control) => <Input {...control} name="name" autoComplete="off" maxLength={200} defaultValue={values["name"] ?? ""} />}
      </FormRow>
      <FormRow idPrefix={prefix} name="kind" label="Tipo" error={errors["kind"]}>
        {(control) => (
          // `key`: React solo aplica el `defaultValue` de un <select> al montarlo y, al terminar la acción, reinicia el formulario a ese valor
          // inicial; sin remontarlo, lo guardado (o lo tecleado, si hubo errores) se perdería.
          <NativeSelect
            key={values["kind"] ?? ""}
            {...control}
            name="kind"
            defaultValue={values["kind"] ?? "business"}
            onChange={(event) => setPicked({ ...current, kind: event.target.value })}
          >
            {CLIENT_KINDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormRow>
      <FormRow idPrefix={prefix} name="country" label="País" error={errors["country"]}>
        {(control) => (
          <NativeSelect
            key={values["country"] ?? ""}
            {...control}
            name="country"
            defaultValue={values["country"] ?? ""}
            onChange={(event) => setPicked({ ...current, country: event.target.value })}
          >
            <option value="">Elige un país</option>
            {countries.map((country) => (
              <option key={country.code} value={country.code}>
                {country.name}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormRow>
      <FormRow idPrefix={prefix} name="tax_id" label={identifier.label} error={errors["tax_id"]} hint={identifier.hint}>
        {(control) => <Input {...control} name="tax_id" autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={64} defaultValue={values["tax_id"] ?? ""} />}
      </FormRow>
      <FormRow idPrefix={prefix} name="address" label="Domicilio" error={errors["address"]}>
        {(control) => <Input {...control} name="address" autoComplete="off" maxLength={300} defaultValue={values["address"] ?? ""} />}
      </FormRow>
    </div>
  );
}

/** «Añadir cliente»: un desplegable nativo (accesible con teclado) con el formulario. */
export function AddClient() {
  const [state, action, pending] = useActionState(createClient, initialFormState);
  const prefix = "cliente-nuevo";
  return (
    // Abierto mientras haya un resultado que leer (error o «Cliente añadido.»): si pasara de `true` a `undefined` tras un error, React quitaría
    // el atributo y el desplegable se cerraría escondiendo el aviso de éxito.
    <details className="rounded-panel border border-rule bg-sheet p-4" open={state.status === "idle" ? undefined : true}>
      <summary className="cursor-pointer text-[15px] font-semibold text-action hover:text-action-hover">Añadir cliente</summary>
      <form action={action} noValidate className="mt-4 grid max-w-4xl gap-4">
        <ErrorSummary state={state} fieldIds={clientFieldIds(prefix)} />
        <ClientFields prefix={prefix} values={state.values ?? NEW_CLIENT} errors={state.fieldErrors ?? {}} source={state} />
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? "Añadiendo…" : "Añadir cliente"}
          </Button>
          <Feedback state={state.status === "error" ? { status: "idle" } : state} />
        </div>
      </form>
    </details>
  );
}
