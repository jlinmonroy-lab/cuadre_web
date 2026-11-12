// Lecturas de «Mi gestor» para los Server Components (list_gestor_accesses, list_gestor_notes, list_gestor_activity). Corren en el servidor con
// el token de la sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible»
// (app/error.tsx): nunca se enseña el cuerpo de un error.
import "server-only";

import { redirect } from "next/navigation";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead } from "@/lib/api-actions";
import { ServiceUnavailableError } from "@/lib/session";

export type ActivityPage = components["schemas"]["ActivityPage"];

/** Los accesos y las invitaciones del autónomo, el más reciente primero (los caducados ya llegan como `expired`). */
export async function listAccesses(): Promise<components["schemas"]["GestorAccess"][]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/gestor/accesos");
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}

/** Las anotaciones que ha dejado el gestor en la cuenta, con el correo de quien las escribió. */
export async function listNotes(): Promise<components["schemas"]["GestorNote"][]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/gestor/anotaciones");
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}

/**
 * Una página del registro de actividad, la más reciente primero. Con un `cursor` que la API no reconoce (manipulado) se vuelve a la primera
 * página: la lista se resuelve recargándola.
 */
export async function listActivity(cursor: string | undefined): Promise<ActivityPage> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/gestor/actividad", { params: { query: cursor ? { cursor } : {} } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  if (cursor && result.response.status === 422) redirect("/gestor");
  return failRead(result.response.status);
}
