// Lecturas del perfil y las series para los Server Components (get_profile, list_invoice_series). Corren en el servidor con el token de la
// sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible» (app/error.tsx):
// nunca se enseña el cuerpo de un error.
import "server-only";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead } from "@/lib/api-actions";
import { ServiceUnavailableError } from "@/lib/session";

export type Profile = components["schemas"]["Profile"];
export type InvoiceSeries = components["schemas"]["InvoiceSeries"];

export async function getProfile(): Promise<Profile> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/profile");
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}

/**
 * El perfil para un AVISO (Inicio, revisión de una factura): si no se puede leer, devuelve `null` y la pantalla sigue sin el aviso en
 * lugar de caerse por algo secundario. Un 401 o un 403 sí redirigen (la sesión o el rol no valen para nada de lo que hay en la pantalla).
 */
export async function getProfileForNotice(): Promise<Profile | null> {
  try {
    return await getProfile();
  } catch (error) {
    if (error instanceof ServiceUnavailableError) return null;
    throw error;
  }
}

/** Las series de la persona: la predeterminada primero y después por código; incluye las archivadas. */
export async function listInvoiceSeries(): Promise<InvoiceSeries[]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/invoice-series");
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}
