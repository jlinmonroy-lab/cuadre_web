// Lectura de los clientes para los Server Components (list_clients). Corre en el servidor con el token de la sesión. Un 401 cierra la sesión
// con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible» (app/error.tsx): nunca se enseña el cuerpo de un error.
import "server-only";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead } from "@/lib/api-actions";
import { ServiceUnavailableError } from "@/lib/session";

export type Client = components["schemas"]["Client"];

/** Los clientes de la persona, ya ordenados por nombre en español; los archivados solo si se piden. */
export async function listClients(includeArchived: boolean): Promise<Client[]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/clients", { params: { query: { include_archived: includeArchived } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}
