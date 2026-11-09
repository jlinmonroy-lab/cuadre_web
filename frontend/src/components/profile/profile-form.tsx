"use client";

import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { initialFormState } from "@/lib/form-state";
import { saveProfile } from "@/lib/profile-actions";
import { RETENTION_OPTIONS } from "@/lib/profile-form";

export type RetentionAdvice = { suggested_rate: string | null; reduced_until_year: number | null; warning: string | null };

const PREFIX = "perfil";
const FIELD_IDS = Object.fromEntries(
  ["legal_name", "tax_id", "fiscal_address", "activity", "iae_epigraph", "activity_start_date", "irpf_rate", "home_pct", "iban"].map((name) => [name, `${PREFIX}-${name}`]),
);

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-4 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

/**
 * Perfil personal y del negocio (RF-004). La interfaz muestra lo que dice el servidor y no valida nada fiscal: el NIF, el IBAN y los rangos
 * los comprueba la API, que devuelve todos los errores a la vez (no se guarda nada si alguno falla) y cada uno aparece junto a su campo.
 */
export function ProfileForm({ initial, retention }: { initial: Record<string, string>; retention: RetentionAdvice }) {
  const [state, action, pending] = useActionState(saveProfile, initialFormState);
  const values = state.values ?? initial;
  const errors = state.fieldErrors ?? {};
  const saved = state.status === "sent";
  // La sugerencia y el aviso salen del servidor con lo YA guardado; si la persona acaba de guardar, `refresh()` los renueva.
  const suggestion =
    retention.suggested_rate !== null && retention.reduced_until_year !== null
      ? `Sugerencia según tu fecha de alta: ${retention.suggested_rate === "7.00" ? "7 %" : "15 %"} (el 7 % vale hasta el ${retention.reduced_until_year}). Es orientativo.`
      : "Indica tu fecha de alta para que te sugiramos la retención. Es orientativo.";

  return (
    <form action={action} noValidate className="grid max-w-4xl gap-6">
      <ErrorSummary state={state} fieldIds={FIELD_IDS} />
      <Section id="perfil-fiscal" title="Datos fiscales">
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
          <FormRow idPrefix={PREFIX} name="legal_name" label="Nombre o razón social" error={errors["legal_name"]}>
            {(control) => <Input {...control} name="legal_name" autoComplete="off" maxLength={200} defaultValue={values["legal_name"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={PREFIX} name="tax_id" label="NIF" error={errors["tax_id"]} hint="NIF, NIE o CIF español.">
            {(control) => <Input {...control} name="tax_id" autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={32} defaultValue={values["tax_id"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={PREFIX} name="fiscal_address" label="Domicilio fiscal" error={errors["fiscal_address"]}>
            {(control) => <Input {...control} name="fiscal_address" autoComplete="off" maxLength={300} defaultValue={values["fiscal_address"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={PREFIX} name="activity" label="Actividad" error={errors["activity"]}>
            {(control) => <Input {...control} name="activity" autoComplete="off" maxLength={200} defaultValue={values["activity"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={PREFIX} name="iae_epigraph" label="Epígrafe del IAE" error={errors["iae_epigraph"]}>
            {(control) => <Input {...control} name="iae_epigraph" autoComplete="off" maxLength={20} defaultValue={values["iae_epigraph"] ?? ""} />}
          </FormRow>
          <FormRow idPrefix={PREFIX} name="activity_start_date" label="Fecha de alta" error={errors["activity_start_date"]}>
            {(control) => <Input {...control} name="activity_start_date" type="date" defaultValue={values["activity_start_date"] ?? ""} />}
          </FormRow>
        </div>
        <p className="text-[13px] text-ink-soft">
          <strong className="font-semibold">Régimen de IVA:</strong> Régimen general (en esta versión es el único disponible).
        </p>
      </Section>

      <Section id="perfil-retencion" title="Retención y vivienda">
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
          <FormRow idPrefix={PREFIX} name="irpf_rate" label="Retención de IRPF" error={errors["irpf_rate"]} hint={suggestion}>
            {(control) => (
              // `key`: React solo aplica el `defaultValue` de un <select> al montarlo, y al terminar la acción reinicia el formulario a ese valor
              // inicial; sin remontarlo, lo guardado (o lo tecleado, si hubo errores) se perdería y un segundo guardado borraría la retención.
              <NativeSelect key={values["irpf_rate"] ?? ""} {...control} name="irpf_rate" defaultValue={values["irpf_rate"] ?? ""}>
                <option value="">Sin elegir</option>
                {RETENTION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormRow>
          <FormRow idPrefix={PREFIX} name="home_pct" label="Vivienda afecta a la actividad (%)" error={errors["home_pct"]} hint="Por ejemplo 30. Solo se guarda: aún no se calcula nada con él.">
            {(control) => <Input {...control} name="home_pct" inputMode="decimal" autoComplete="off" className="text-right tabular-nums" defaultValue={values["home_pct"] ?? ""} />}
          </FormRow>
        </div>
        {retention.warning ? (
          <p className="rounded-md border border-status-doubt-line bg-status-doubt-bg px-3 py-2 text-sm font-semibold text-status-doubt">
            Aviso (orientativo): {retention.warning}
          </p>
        ) : null}
      </Section>

      <Section id="perfil-cobros" title="Cobros">
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
          <FormRow idPrefix={PREFIX} name="iban" label="IBAN" error={errors["iban"]} hint="Se muestra agrupado de cuatro en cuatro. Solo lo ves tú y tu gestor.">
            {(control) => <Input {...control} name="iban" autoComplete="off" spellCheck={false} maxLength={64} defaultValue={values["iban"] ?? ""} />}
          </FormRow>
        </div>
      </Section>

      <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-5">
        <Button type="submit" disabled={pending}>
          {pending ? "Guardando…" : "Guardar"}
        </Button>
        <p aria-live="polite" className="text-sm font-semibold text-status-ok">
          {saved ? (state.message ?? "Cambios guardados.") : ""}
        </p>
      </div>
    </form>
  );
}
