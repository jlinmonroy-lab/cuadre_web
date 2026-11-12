"use server";

// Server Actions de «Mi gestor»: invitar y revocar. Son CORTAS (no esperan a ningún servicio externo: el correo lo envía la API tras confirmar
// la invitación y, si falla, la respuesta lo dice con `email_sent`). Todo lo que reciben es entrada no confiable (las Server Actions son POST
// públicos y el proxy no las ve): se valida la forma aquí, se comprueba la sesión y la API vuelve a decidir (403 al gestor, 404 al acceso
// ajeno, 409 y 422 con su texto). Ninguna regla de acceso vive aquí. El correo de un gestor no se escribe en ningún registro.
import { refresh } from "next/cache";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import type { FormState } from "@/lib/form-state";
import { fieldErrorsFromInviteProblem, inviteMessage, toInviteBody, valuesFromInviteForm } from "@/lib/gestor-form";
import { isUuid } from "@/lib/gestor";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";

const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };
const UNKNOWN_ACCESS: FormState = { status: "error", message: "No encontramos ese acceso." };

/** «Invitar»: crea la invitación y la API manda el correo. La respuesta no revela si la persona existe. */
export async function inviteGestor(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromInviteForm((name) => formData.get(name));
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/gestor/accesos", { body: toInviteBody(values) });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    // Sin `values`: el campo se vacía para la siguiente invitación.
    return { status: "sent", message: inviteMessage(result.data) };
  }
  const problem = problemOf(result.response, result.error);
  const fieldErrors = fieldErrorsFromInviteProblem(problem);
  // Un error del correo se lee junto al campo; el titular solo se añade si dice algo más que él (el límite de invitaciones, un fallo del servicio).
  return fieldErrors ? { status: "error", fieldErrors, values } : { status: "error", message: problem.message, values };
}

/** «Revocar»: retira una invitación pendiente o un acceso activo. El gestor deja de ver la contabilidad en la petición siguiente. */
export async function revokeGestorAccess(accessId: string): Promise<FormState> {
  if (!isUuid(accessId)) return UNKNOWN_ACCESS;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/gestor/accesos/{access_id}/revocar", { params: { path: { access_id: accessId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.response.ok) {
    refresh();
    return { status: "sent", message: "Acceso revocado. Tu gestor ya no puede ver tu contabilidad." };
  }
  const problem = problemOf(result.response, result.error);
  // Un acceso que ya no existe o que ya no está abierto: la lista cambió (p. ej. el gestor lo rechazó a la vez), se recarga para que lo diga.
  if (problem.status === 404 || problem.status === 409) refresh();
  return { status: "error", message: problem.message };
}
