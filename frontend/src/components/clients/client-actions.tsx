"use client";

import { useActionState } from "react";

import type { components } from "@/api/schema";
import { ErrorSummary } from "@/components/error-summary";
import { Button } from "@/components/ui/button";
import { ClientFields, Feedback, clientFieldIds } from "@/components/clients/client-form";
import { setClientArchived, updateClient } from "@/lib/clients-actions";
import { valuesFromClient } from "@/lib/clients-form";
import { initialFormState, type FormState } from "@/lib/form-state";

export type ClientRow = components["schemas"]["Client"];

/** Editar un cliente: sustituye todos los datos y el servidor vuelve a calcular el ámbito y el estado de VIES. */
export function ClientEditor({ client, view, onClose }: { client: ClientRow; view: "tarjeta" | "tabla"; onClose: () => void }) {
  const [state, action, pending] = useActionState(updateClient.bind(null, client.id), initialFormState);
  const prefix = `cliente-${view}-${client.id}`;
  return (
    <form action={action} noValidate className="grid max-w-4xl gap-3 rounded-md border border-rule bg-white p-3">
      <ErrorSummary state={state} fieldIds={clientFieldIds(prefix)} />
      <ClientFields prefix={prefix} values={state.values ?? valuesFromClient(client)} errors={state.fieldErrors ?? {}} source={state} />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Guardando…" : "Guardar cliente"}
        </Button>
        <Button type="button" variant="outline" onClick={onClose}>
          Cerrar
        </Button>
        <Feedback state={state.status === "error" ? { status: "idle" } : state} />
      </div>
    </form>
  );
}

/**
 * Las acciones de un cliente: «Editar» (solo si está activo: el servidor rechaza editar un archivado) y «Archivar» / «Reactivar». Un cliente no
 * se borra. El resultado de archivar o reactivar se avisa también en la lista (la fila cambia de sitio o desaparece, y el aviso sigue ahí).
 */
export function ClientActions({
  client,
  editing,
  onToggleEdit,
  onNotice,
}: {
  client: ClientRow;
  editing: boolean;
  onToggleEdit: () => void;
  onNotice: (message: string) => void;
}) {
  // Un único estado por cliente: el mensaje que se enseña es siempre el de la ÚLTIMA acción.
  const [state, action, pending] = useActionState(async (): Promise<FormState> => {
    const next = await setClientArchived(client.id, !client.archived);
    if (next.status === "sent") onNotice(`${next.message ?? ""} ${client.name}`.trim());
    return next;
  }, initialFormState);
  const name = `cliente ${client.name}`;
  return (
    <div className="grid gap-2">
      <form action={action} className="flex flex-wrap gap-2">
        {!client.archived ? (
          <Button type="button" variant="outline" size="sm" aria-expanded={editing} aria-label={`Editar el ${name}`} onClick={onToggleEdit}>
            Editar
          </Button>
        ) : null}
        <Button type="submit" variant="outline" size="sm" disabled={pending} aria-label={`${client.archived ? "Reactivar" : "Archivar"} el ${name}`}>
          {client.archived ? "Reactivar" : "Archivar"}
        </Button>
      </form>
      <Feedback state={state.status === "sent" ? { status: "idle" } : state} />
    </div>
  );
}
