// Lectura de los borradores de los modelos 303 y 130 para el Server Component de /trimestres (get_modelo_303 y get_modelo_130). Corre en el servidor con
// el token de la sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo que no sea un 422 conocido es «servicio no disponible»
// (app/error.tsx): nunca se enseña el cuerpo de un error. Un 422 (trimestre futuro, periodo demasiado grande, tipo de IVA ilegible en el 303) es algo que
// la pantalla explica con el texto en español de la API.
import "server-only";

import { authenticatedApi, failRead, problemOf } from "@/lib/api-actions";
import { ServiceUnavailableError } from "@/lib/session";
import type { Modelo130, Modelo303, QuarterQuery } from "@/lib/tax";

export type TaxReading<M> = { status: "ok"; model: M } | { status: "problem"; code: string; message: string };

type Outcome<M> = { data?: M; error?: unknown; response: Response };

/** El tratamiento común de la respuesta de un borrador. */
function reading<M>(result: Outcome<M>): TaxReading<M> {
  if (result.data) return { status: "ok", model: result.data };
  if (result.response.status === 422) {
    const problem = problemOf(result.response, result.error);
    return { status: "problem", code: problem.code, message: problem.message };
  }
  return failRead(result.response.status);
}

/** El borrador del 303 del trimestre pedido. */
export async function getModelo303(query: QuarterQuery): Promise<TaxReading<Modelo303>> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/tax/303", { params: { query: { year: query.year, quarter: query.quarter } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  return reading(result);
}

/** El borrador del 130 del trimestre pedido, acumulado desde el 1 de enero. */
export async function getModelo130(query: QuarterQuery): Promise<TaxReading<Modelo130>> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/tax/130", { params: { query: { year: query.year, quarter: query.quarter } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  return reading(result);
}
