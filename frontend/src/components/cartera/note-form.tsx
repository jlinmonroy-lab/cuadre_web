"use client";

import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Feedback } from "@/components/gestor/feedback";
import { Button } from "@/components/ui/button";
import { initialFormState } from "@/lib/form-state";
import { createNote } from "@/lib/gestor-cartera-actions";

/**
 * «Añadir anotación»: texto de 1 a 2.000 caracteres para el autónomo. Solo se añaden: no se editan ni se borran. Desde el detalle de una factura (`invoiceId`)
 * la anotación queda ligada a ella. El error va junto al campo; lo que se enlaza lo comprueba el servidor.
 */
export function NoteForm({ ownerId, invoiceId = null, title }: { ownerId: string; invoiceId?: string | null; title: string }) {
  const [state, action, pending] = useActionState(createNote.bind(null, ownerId, invoiceId), initialFormState);
  const prefix = invoiceId === null ? "anotacion" : "anotacion-factura";
  return (
    <form action={action} noValidate className="grid max-w-3xl gap-3 rounded-panel border border-rule bg-sheet p-4">
      <ErrorSummary state={state} fieldIds={{ body: `${prefix}-body` }} />
      <FormRow
        idPrefix={prefix}
        name="body"
        label={title}
        hint="Entre 1 y 2.000 caracteres. El autónomo la verá y no se puede editar ni borrar."
        error={state.fieldErrors?.["body"]}
      >
        {(control) => (
          <textarea
            {...control}
            name="body"
            rows={4}
            maxLength={2000}
            defaultValue={state.values?.["body"] ?? ""}
            className="min-h-24 w-full rounded-lg border border-input bg-white px-3 py-2 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/60 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20"
          />
        )}
      </FormRow>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Guardando…" : "Añadir anotación"}
        </Button>
        <Feedback state={state.status === "error" ? { status: "idle" } : state} />
      </div>
    </form>
  );
}
