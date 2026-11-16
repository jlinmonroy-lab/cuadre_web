// Lectura del reporte mensual para el Server Component de /reporte (get_monthly_report). Corre en el servidor con el token de la sesión. Mismo manejo de
// errores que la contabilidad mensual: un 401 cierra la sesión con aviso, un 403 lleva a /403, un 404 o un 422 se explican con el texto en español de la API y
// cualquier otro fallo es «servicio no disponible» (app/error.tsx): nunca se enseña el cuerpo de un error.
import "server-only";

import { authenticatedApi } from "@/lib/api-actions";
import { reading, type MonthlyReading } from "@/lib/monthly-api";
import type { MonthlyReport } from "@/lib/report";
import { ServiceUnavailableError } from "@/lib/session";

/** El reporte de un mes: cifras, comparación, ámbitos, gastos por categoría y tendencia. */
export async function getMonthlyReport(year: number, month: number): Promise<MonthlyReading<MonthlyReport>> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/monthly-report/{year}/{month}", { params: { path: { year, month } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  return reading(result);
}
