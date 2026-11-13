// Lectura de los ajustes de recordatorios para el Server Component de /perfil (get_reminder_settings). Corre en el servidor con el token de la
// sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible» (app/error.tsx).
import "server-only";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead } from "@/lib/api-actions";
import { ServiceUnavailableError } from "@/lib/session";

export type ReminderSettings = components["schemas"]["ReminderSettings"];

export async function getReminderSettings(): Promise<ReminderSettings> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/me/reminders");
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}
