// Ayudas comunes de lo que corre en el servidor de Next y habla con la API en nombre de la persona (gastos).
// 401 y 403 no se "muestran": llevan a donde corresponde. Lo demás se devuelve para pintarlo junto a la acción.
import "server-only";

import { redirect } from "next/navigation";

import { apiFor, sessionToken } from "@/lib/api-server";
import { describeProblem, type Problem } from "@/lib/problems";
import { ServiceUnavailableError } from "@/lib/session";

export type Api = ReturnType<typeof apiFor>;

/** El cliente de la API con el token de la sesión, o a /login si no hay sesión. */
export async function authenticatedApi(): Promise<Api> {
  const token = await sessionToken();
  if (!token) redirect("/login");
  return apiFor(token);
}

/** Qué hacer con un estado inesperado al LEER: 401 cierra la sesión con aviso, 403 va a /403 y lo demás es «servicio no disponible». */
export function failRead(status: number): never {
  if (status === 401) redirect("/auth/cerrar?aviso=sesion");
  if (status === 403) redirect("/403");
  throw new ServiceUnavailableError();
}

/** El problema de una respuesta de error de la API para pintarlo; 401 y 403 redirigen y no vuelven. */
export function problemOf(response: Response, error: unknown): Problem {
  if (response.status === 401) redirect("/auth/cerrar?aviso=sesion");
  if (response.status === 403) redirect("/403");
  return describeProblem({ status: response.status, body: error, retryAfter: response.headers.get("retry-after") });
}
