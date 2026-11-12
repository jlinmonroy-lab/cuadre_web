// Lecturas del gestor para los Server Components de /cartera (cartera, invitaciones y la ficha de cada autónomo). Corren en el servidor con el token de la
// sesión del GESTOR (nunca el del autónomo). Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible»
// (app/error.tsx): nunca se enseña el cuerpo de un error. Un `404` es el uniforme de la API (sin vínculo, revocado, de otro gestor o inexistente): se
// devuelve `null` y la página dice «no encontrado», igual en todos los casos.
import "server-only";

import { redirect } from "next/navigation";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead, problemOf } from "@/lib/api-actions";
import { PAGE_SIZE, fichaHref, pageOffset, type GestorInvitation, type PortfolioEntry } from "@/lib/gestor-cartera";
import type { Invoice, ListQuery } from "@/lib/invoices";
import { ServiceUnavailableError } from "@/lib/session";
import type { Modelo130, Modelo303, QuarterQuery } from "@/lib/tax";
import type { TaxReading } from "@/lib/tax-api";

export type AutonomoSummary = components["schemas"]["AutonomoSummary"];
export type OwnerExpensePage = components["schemas"]["ExpenseListPage"];
export type OwnerDocument = components["schemas"]["DocumentSummary"];
export type OwnerProfileView = components["schemas"]["ProfileView"];
export type OwnerClient = components["schemas"]["Client"];
export type OwnerNote = components["schemas"]["GestorNote"];

type Outcome<T> = { data?: T; response: Response };

/** La lectura de un recurso del autónomo: el dato, o `null` si la API contesta el `404` uniforme. */
async function read<T>(run: (api: Awaited<ReturnType<typeof authenticatedApi>>) => Promise<Outcome<T>>): Promise<T | null> {
  const api = await authenticatedApi();
  let result: Outcome<T>;
  try {
    result = await run(api);
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data !== undefined) return result.data;
  if (result.response.status === 404) return null;
  return failRead(result.response.status);
}

/** Una lectura que no tiene `404` (la cartera y las invitaciones son del propio gestor). */
async function readOwn<T>(run: (api: Awaited<ReturnType<typeof authenticatedApi>>) => Promise<Outcome<T>>): Promise<T> {
  const data = await read(run);
  if (data === null) throw new ServiceUnavailableError();
  return data;
}

export const getPortfolio = (): Promise<PortfolioEntry[]> => readOwn((api) => api.GET("/api/gestor/cartera"));

export const listInvitations = (): Promise<GestorInvitation[]> => readOwn((api) => api.GET("/api/gestor/invitaciones"));

export const getAutonomo = (ownerId: string): Promise<AutonomoSummary | null> =>
  read((api) => api.GET("/api/gestor/autonomos/{owner_id}", { params: { path: { owner_id: ownerId } } }));

/** Una página de facturas: hasta `PAGE_SIZE + 1` filas (la de más solo sirve para saber si hay otra página). */
export const listOwnerInvoices = (ownerId: string, query: ListQuery, page: number): Promise<Invoice[] | null> =>
  read((api) =>
    api.GET("/api/gestor/autonomos/{owner_id}/facturas", {
      params: {
        path: { owner_id: ownerId },
        query: { year: query.year, scope: query.scope ?? null, paid: query.paid ?? null, limit: PAGE_SIZE + 1, offset: pageOffset(page) },
      },
    }),
  );

export const getOwnerInvoice = (ownerId: string, invoiceId: string): Promise<Invoice | null> =>
  read((api) => api.GET("/api/gestor/autonomos/{owner_id}/facturas/{invoice_id}", { params: { path: { owner_id: ownerId, invoice_id: invoiceId } } }));

/**
 * Una página de gastos, los anulados incluidos (llevan `voided_at`). Con un cursor que la API no reconoce (manipulado) se vuelve a la primera página:
 * la lista se resuelve recargándola.
 */
export async function listOwnerExpenses(ownerId: string, cursor: string | null): Promise<OwnerExpensePage | null> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/gestor/autonomos/{owner_id}/gastos", { params: { path: { owner_id: ownerId }, query: { limit: PAGE_SIZE, page: cursor } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data !== undefined) return result.data;
  if (result.response.status === 404) return null;
  if (cursor !== null && result.response.status === 422) redirect(fichaHref(ownerId, "gastos"));
  return failRead(result.response.status);
}

export const listOwnerDocuments = (ownerId: string): Promise<OwnerDocument[] | null> =>
  read((api) => api.GET("/api/gestor/autonomos/{owner_id}/documentos", { params: { path: { owner_id: ownerId } } }));

export const getOwnerProfile = (ownerId: string): Promise<OwnerProfileView | null> =>
  read((api) => api.GET("/api/gestor/autonomos/{owner_id}/perfil", { params: { path: { owner_id: ownerId } } }));

export const listOwnerClients = (ownerId: string): Promise<OwnerClient[] | null> =>
  read((api) => api.GET("/api/gestor/autonomos/{owner_id}/clientes", { params: { path: { owner_id: ownerId } } }));

export const listOwnerNotes = (ownerId: string): Promise<OwnerNote[] | null> =>
  read((api) => api.GET("/api/gestor/autonomos/{owner_id}/anotaciones", { params: { path: { owner_id: ownerId } } }));

/** El tratamiento común de un borrador: el `404` es «no encontrado» y el `422` (trimestre futuro, periodo demasiado grande) lo explica la pantalla. */
async function taxReading<M>(run: (api: Awaited<ReturnType<typeof authenticatedApi>>) => Promise<Outcome<M> & { error?: unknown }>): Promise<TaxReading<M> | null> {
  const api = await authenticatedApi();
  let result: Outcome<M> & { error?: unknown };
  try {
    result = await run(api);
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data !== undefined) return { status: "ok", model: result.data };
  if (result.response.status === 404) return null;
  if (result.response.status === 422) {
    const problem = problemOf(result.response, result.error);
    return { status: "problem", code: problem.code, message: problem.message };
  }
  return failRead(result.response.status);
}

export const getOwnerModelo303 = (ownerId: string, query: QuarterQuery): Promise<TaxReading<Modelo303> | null> =>
  taxReading((api) =>
    api.GET("/api/gestor/autonomos/{owner_id}/trimestres/303", { params: { path: { owner_id: ownerId }, query: { year: query.year, quarter: query.quarter } } }),
  );

export const getOwnerModelo130 = (ownerId: string, query: QuarterQuery): Promise<TaxReading<Modelo130> | null> =>
  taxReading((api) =>
    api.GET("/api/gestor/autonomos/{owner_id}/trimestres/130", { params: { path: { owner_id: ownerId }, query: { year: query.year, quarter: query.quarter } } }),
  );
