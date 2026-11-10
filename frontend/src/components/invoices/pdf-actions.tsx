"use client";

import { useActionState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { initialFormState, type FormState } from "@/lib/form-state";
import { generateInvoicePdf } from "@/lib/invoices-actions";

/**
 * El PDF de la factura. Con el PDF listo, «Descargar PDF» apunta al Route Handler del servidor (la web nunca ve la URL de Storage). Sin PDF
 * (`pending`: la subida falló al emitir, o la factura es anterior), «Generar PDF» lo crea; es idempotente y puede tardar unos segundos, así que lo
 * dice y lo anuncia en una región `aria-live`.
 */
export function PdfActions({ invoiceId, ready }: { invoiceId: string; ready: boolean }) {
  const [state, action, pending] = useActionState(async (): Promise<FormState> => generateInvoicePdf(invoiceId), initialFormState);
  if (ready) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <a href={`/facturas/${invoiceId}/pdf`} className={buttonVariants({ variant: "default" })}>
          Descargar PDF
        </a>
        <p aria-live="polite" className="text-[13px] font-semibold text-status-ok">
          {state.status === "sent" ? (state.message ?? "") : ""}
        </p>
      </div>
    );
  }
  return (
    <form action={action} className="grid gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Generando PDF…" : "Generar PDF"}
        </Button>
        <p className="text-[13px] text-ink-soft">Esta factura aún no tiene PDF.</p>
      </div>
      <p aria-live="polite" className={`text-[13px] font-semibold ${state.status === "error" ? "text-status-error" : "text-ink-soft"}`}>
        {pending ? "Generando el PDF; puede tardar unos segundos." : state.status === "idle" ? "" : (state.message ?? "")}
      </p>
    </form>
  );
}
