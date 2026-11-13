// Lectura de la contabilidad mensual para el Server Component de /mensual (get_monthly_closings y get_monthly_closing). Corre en el servidor con el token de la
// sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo que no sea un 404 o un 422 conocido es «servicio no disponible»
// (app/error.tsx): nunca se enseña el cuerpo de un error. Un año futuro (422) es algo que la pantalla explica con el texto en español de la API.
import "server-only";

import { authenticatedApi, failRead, problemOf } from "@/lib/api-actions";
import type { MonthlyClosing, MonthlyClosings } from "@/lib/monthly";
import { ServiceUnavailableError } from "@/lib/session";

export type MonthlyReading<M> = { status: "ok"; data: M } | { status: "problem"; code: string; message: string };

type Outcome<M> = { data?: M; error?: unknown; response: Response };

function reading<M>(result: Outcome<M>): MonthlyReading<M> {
  if (result.data) return { status: "ok", data: result.data };
  if (result.response.status === 404 || result.response.status === 422) {
    const problem = problemOf(result.response, result.error);
    return { status: "problem", code: problem.code, message: problem.message };
  }
  return failRead(result.response.status);
}

/** Los meses del año con sus totales, el acumulado y el estado del cierre. */
export async function getMonthlyClosings(year: number): Promise<MonthlyReading<MonthlyClosings>> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/monthly-closings", { params: { query: { year } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  return reading(result);
}

/** Un mes con sus ingresos por cliente y ámbito. */
export async function getMonthlyClosing(year: number, month: number): Promise<MonthlyReading<MonthlyClosing>> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/monthly-closings/{year}/{month}", { params: { path: { year, month } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  return reading(result);
}
