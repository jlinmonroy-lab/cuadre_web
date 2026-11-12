"use server";

// Server Actions del gestor: aceptar o rechazar una invitación y dejar una anotación. Son CORTAS (no esperan a ningún servicio externo). Todo lo que reciben
// es entrada no confiable (las Server Actions son POST públicos y el proxy no las ve): se valida la forma aquí, se comprueba la sesión y la API vuelve a
// decidir (403 al autónomo, 404 sin vínculo, 409 y 422 con su texto). Ninguna regla de acceso vive aquí. El texto de una anotación no se escribe en ningún
// registro.
import { refresh } from "next/cache";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import type { FormState } from "@/lib/form-state";
import { fieldErrorsFromNoteProblem, toNoteBody, valuesFromNoteForm } from "@/lib/gestor-cartera";
import { isUuid } from "@/lib/gestor";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";

const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };
const UNKNOWN_INVITATION: FormState = { status: "error", message: "No encontramos esa invitación." };

/** «Aceptar»: el autónomo pasa a la cartera con vínculo activo. */
export async function acceptInvitation(accessId: string): Promise<FormState> {
  if (!isUuid(accessId)) return UNKNOWN_INVITATION;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/gestor/invitaciones/{access_id}/aceptar", { params: { path: { access_id: accessId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.response.ok) {
    refresh();
    return { status: "sent", message: "Invitación aceptada." };
  }
  const problem = problemOf(result.response, result.error);
  // Una invitación que ya no está (el autónomo la revocó, caducó o ya se respondió): se recarga para que la lista lo diga.
  if (problem.status === 404 || problem.status === 409) refresh();
  return { status: "error", message: problem.message };
}

/** «Rechazar»: la invitación pasa a rechazada y no vuelve a salir. */
export async function declineInvitation(accessId: string): Promise<FormState> {
  if (!isUuid(accessId)) return UNKNOWN_INVITATION;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/gestor/invitaciones/{access_id}/rechazar", { params: { path: { access_id: accessId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.response.ok) {
    refresh();
    return { status: "sent", message: "Invitación rechazada." };
  }
  const problem = problemOf(result.response, result.error);
  if (problem.status === 404 || problem.status === 409) refresh();
  return { status: "error", message: problem.message };
}

/**
 * «Añadir anotación» (`useActionState` con el autónomo y, si se anota desde una factura, la factura enlazados). Solo se añaden: no hay edición ni borrado.
 * El servidor comprueba que el vínculo siga activo y que lo enlazado sea de este autónomo.
 */
export async function createNote(ownerId: string, invoiceId: string | null, _previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromNoteForm((name) => formData.get(name));
  if (!isUuid(ownerId)) return { status: "error", message: "No encontramos a ese autónomo.", values };
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/gestor/autonomos/{owner_id}/anotaciones", { params: { path: { owner_id: ownerId } }, body: toNoteBody(values, invoiceId) });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    // Sin `values`: el campo se vacía para la siguiente anotación.
    return { status: "sent", message: "Anotación guardada." };
  }
  const problem = problemOf(result.response, result.error);
  const fieldErrors = fieldErrorsFromNoteProblem(problem);
  return fieldErrors ? { status: "error", fieldErrors, values } : { status: "error", message: problem.message, values };
}
