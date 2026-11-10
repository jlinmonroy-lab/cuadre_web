"use client";

import Link from "next/link";
import { useActionState, useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { InvoicePreview, type PreviewView } from "@/components/invoices/invoice-preview";
import { CompleteProfileNotice } from "@/components/profile/complete-profile-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { initialFormState } from "@/lib/form-state";
import type { PreviewReply } from "@/lib/invoice-handlers";
import { issueInvoice } from "@/lib/invoices-actions";
import { INVOICE_FORM_FIELDS, type InvoiceFormState } from "@/lib/invoices-form";

export type ClientOption = { id: string; name: string; hasAddress: boolean };
export type SeriesOption = { id: string; code: string; isDefault: boolean };

const PREFIX = "factura-nueva";
const fieldIds: Record<string, string> = Object.fromEntries(INVOICE_FORM_FIELDS.map((name) => [name, `${PREFIX}-${name}`]));
const DEBOUNCE_MS = 300;
const VAT_RATES = ["21", "10", "4"] as const;

/** Los valores del formulario tal como están ahora mismo (para la vista previa; el servidor vuelve a validarlo todo al emitir). */
function currentValues(form: HTMLFormElement): Record<string, string> {
  const data = new FormData(form);
  return Object.fromEntries(INVOICE_FORM_FIELDS.map((name) => [name, typeof data.get(name) === "string" ? (data.get(name) as string) : ""]));
}

/**
 * «Nueva factura»: un desplegable nativo con el formulario y, debajo, la vista previa que sirve la API (ámbito, IVA, retención, total y mención)
 * ANTES de emitir. La interfaz no calcula nada: cada cambio (con una espera de 300 ms) pide la vista previa al servidor y solo vale la última
 * petición. El selector de IVA solo existe cuando el servidor dice que ese cliente lo admite.
 */
export function NewInvoice({ clients, series, today }: { clients: ClientOption[]; series: SeriesOption[]; today: string }) {
  const formRef = useRef<HTMLFormElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const controller = useRef<AbortController | undefined>(undefined);
  const [view, setView] = useState<PreviewView>({ status: "empty" });
  const [vatEditable, setVatEditable] = useState(false);

  const refreshPreview = useCallback((resetVat = false) => {
    clearTimeout(timer.current);
    controller.current?.abort();
    const form = formRef.current;
    if (!form) return;
    const current = currentValues(form);
    // Al cambiar de cliente se olvida el tipo de IVA elegido: el nuevo cliente puede no admitirlo y, si lo admite, empieza en el 21 %.
    if (resetVat) {
      current["vat_rate"] = "";
      setVatEditable(false);
    }
    if (current["client_id"] === "") {
      setVatEditable(false);
      setView({ status: "empty" });
      return;
    }
    setView({ status: "loading" });
    timer.current = setTimeout(async () => {
      const abort = new AbortController();
      controller.current = abort;
      try {
        const response = await fetch("/facturas/vista-previa", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(current),
          signal: abort.signal,
        });
        const reply = (await response.json()) as PreviewReply;
        if (abort.signal.aborted) return;
        setVatEditable(reply.status === "ok" && reply.preview.vat_editable);
        setView({ status: "ready", reply });
      } catch {
        if (!abort.signal.aborted) setView({ status: "failed" });
      }
    }, DEBOUNCE_MS);
  }, []);

  // Tras un error del servidor el formulario vuelve a sus valores: la vista previa se pone al día con lo que hay escrito.
  const [state, action, pending] = useActionState<InvoiceFormState, FormData>(async (previous, formData) => {
    const next = await issueInvoice(previous, formData);
    if (next.status === "error") refreshPreview(false);
    return next;
  }, initialFormState);
  const values = state.values ?? {};
  const errors = state.fieldErrors ?? {};

  // Al salir de la página se cancela lo pendiente.
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      controller.current?.abort();
    },
    [],
  );

  // El concepto no cambia nada de la vista previa: teclearlo no la recalcula.
  const onFormChange = (event: ChangeEvent<HTMLFormElement>) => {
    const name = (event.target as unknown as { name?: string }).name;
    if (name !== "concept") refreshPreview(name === "client_id");
  };

  const clientValue = values["client_id"] ?? "";
  const vatDefault = values["vat_rate"] || "21";

  return (
    // Abierto mientras haya un resultado que leer (un error): si pasara de `true` a `undefined` React quitaría el atributo y se cerraría.
    <details className="rounded-panel border border-rule bg-sheet p-4" open={state.status === "idle" ? undefined : true}>
      <summary className="cursor-pointer text-[15px] font-semibold text-action hover:text-action-hover">Nueva factura</summary>
      {clients.length === 0 ? (
        <p className="mt-4 text-[15px]">
          Para emitir una factura necesitas al menos un cliente activo con domicilio.{" "}
          <Link href="/clientes" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
            Añadir un cliente
          </Link>
        </p>
      ) : (
        <form ref={formRef} action={action} noValidate onChange={onFormChange} className="mt-4 grid max-w-4xl gap-4">
          <ErrorSummary state={state} fieldIds={fieldIds} />
          {state.code === "profile_incomplete" && state.missing ? <CompleteProfileNotice missing={state.missing} /> : null}
          {state.code === "irpf_rate_missing" ? (
            <p className="text-sm">
              <Link href="/perfil" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                Elegir mi retención en el perfil
              </Link>
            </p>
          ) : null}
          {state.code === "client_not_billable" ? (
            <p className="text-sm">
              <Link href="/clientes" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                Ir a Clientes para completar o reactivar al cliente
              </Link>
            </p>
          ) : null}

          <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(240px,1fr))]">
            <FormRow idPrefix={PREFIX} name="client_id" label="Cliente" error={errors["client_id"]}>
              {(control) => (
                // `key`: React solo aplica el `defaultValue` de un <select> al montarlo y, al terminar la acción, reinicia el formulario a ese valor.
                <NativeSelect key={clientValue} {...control} name="client_id" defaultValue={clientValue}>
                  <option value="">Elige un cliente</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.hasAddress ? client.name : `${client.name} (falta el domicilio)`}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormRow>
            <FormRow idPrefix={PREFIX} name="series_id" label="Serie" error={errors["series_id"]} hint="Si no eliges, se usa la predeterminada.">
              {(control) => (
                <NativeSelect key={values["series_id"] ?? ""} {...control} name="series_id" defaultValue={values["series_id"] ?? ""}>
                  <option value="">Serie predeterminada</option>
                  {series.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.code}
                      {item.isDefault ? " (predeterminada)" : ""}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormRow>
            <FormRow idPrefix={PREFIX} name="issue_date" label="Fecha de expedición" error={errors["issue_date"]}>
              {(control) => <Input {...control} name="issue_date" type="date" max={today} defaultValue={values["issue_date"] ?? today} />}
            </FormRow>
            <FormRow idPrefix={PREFIX} name="base" label="Base imponible (€)" error={errors["base"]} hint="En euros, por ejemplo 1.200,00.">
              {(control) => <Input {...control} name="base" inputMode="decimal" autoComplete="off" placeholder="1.200,00" defaultValue={values["base"] ?? ""} />}
            </FormRow>
            {vatEditable ? (
              <FormRow idPrefix={PREFIX} name="vat_rate" label="Tipo de IVA" error={errors["vat_rate"]}>
                {(control) => (
                  <NativeSelect key={`${clientValue}-${vatDefault}`} {...control} name="vat_rate" defaultValue={vatDefault}>
                    {VAT_RATES.map((rate) => (
                      <option key={rate} value={rate}>
                        {rate} %
                      </option>
                    ))}
                  </NativeSelect>
                )}
              </FormRow>
            ) : null}
            <div className="[grid-column:1/-1]">
              <FormRow idPrefix={PREFIX} name="concept" label="Concepto" error={errors["concept"]}>
                {(control) => <Input {...control} name="concept" autoComplete="off" maxLength={300} placeholder="Diseño de identidad visual" defaultValue={values["concept"] ?? ""} />}
              </FormRow>
            </div>
          </div>

          <InvoicePreview view={view} />

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button type="submit" disabled={pending}>
              {pending ? "Emitiendo…" : "Emitir factura"}
            </Button>
            <p className="text-[13px] text-ink-soft" aria-live="polite">
              {pending ? "Estamos emitiendo la factura y preparando su PDF; puede tardar unos segundos." : "Al emitirla recibe su número y ya no se puede modificar."}
            </p>
          </div>
        </form>
      )}
    </details>
  );
}
