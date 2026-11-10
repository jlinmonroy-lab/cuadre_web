"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { initialFormState, type FormState } from "@/lib/form-state";
import { setInvoicePaid } from "@/lib/invoices-actions";

/**
 * «Marcar como cobrada» / «Marcar como pendiente». Es lo único que se puede cambiar en una factura emitida (`paid_at`). El resultado se anuncia en
 * una región `aria-live`; el estado de cobro de la página se actualiza al refrescar la lectura.
 */
export function PaymentButton({ invoiceId, paid }: { invoiceId: string; paid: boolean }) {
  const [state, action, pending] = useActionState(async (): Promise<FormState> => setInvoicePaid(invoiceId, !paid), initialFormState);
  return (
    <form action={action} className="flex flex-wrap items-center gap-3">
      <Button type="submit" variant="outline" disabled={pending}>
        {pending ? "Guardando…" : paid ? "Marcar como pendiente" : "Marcar como cobrada"}
      </Button>
      <p aria-live="polite" className={`text-[13px] font-semibold ${state.status === "error" ? "text-status-error" : "text-status-ok"}`}>
        {state.status === "idle" ? "" : (state.message ?? "")}
      </p>
    </form>
  );
}
