// Lecturas de facturas para los Server Components (list_invoices, get_invoice, get_clients_billing, preview_invoice). Corren en el servidor con el
// token de la sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible»
// (app/error.tsx): nunca se enseña el cuerpo de un error.
import "server-only";

import { unstable_rethrow } from "next/navigation";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead, problemOf } from "@/lib/api-actions";
import type { Client } from "@/lib/clients-api";
import { conditionsText, madridToday, type Conditions, type Invoice, type ListQuery } from "@/lib/invoices";
import { isInvoiceId } from "@/lib/invoices-form";
import { ServiceUnavailableError } from "@/lib/session";

export type ClientBilling = components["schemas"]["ClientBilling"];

/** Las facturas del año (las más recientes primero, como las manda la API), con los filtros de la dirección. */
export async function listInvoices(query: ListQuery): Promise<Invoice[]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/invoices", {
      params: { query: { year: query.year, ...(query.scope ? { scope: query.scope } : {}), ...(query.paid === undefined ? {} : { paid: query.paid }) } },
    });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return failRead(result.response.status);
}

/** La factura, o `null` si no existe (también si es de otra persona: la API no lo distingue). */
export async function getInvoice(id: string): Promise<Invoice | null> {
  if (!isInvoiceId(id)) return null;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/invoices/{invoice_id}", { params: { path: { invoice_id: id } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return result.response.status === 404 ? null : failRead(result.response.status);
}

/** Lo facturado a cada cliente en el año (suma de bases con signo), por id de cliente. Los clientes sin facturas no aparecen. */
export async function getBilledByClient(year: number): Promise<Map<string, number>> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/clients/billing", { params: { query: { year } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (!result.data) return failRead(result.response.status);
  return new Map(result.data.map((row) => [row.client_id, row.billed_cents]));
}

const EXAMPLE_BASE_CENTS = 100_000;

/**
 * Las condiciones de facturación de cada cliente ACTIVO, tal como las devuelve `preview_invoice` con una base de ejemplo: la frase sale de los
 * campos del servidor (tipo de IVA, retención y mención). Una petición por cliente, en paralelo; el fallo de una no tumba la pantalla.
 */
export async function getClientConditions(clients: Client[]): Promise<Map<string, Conditions>> {
  const api = await authenticatedApi();
  const today = madridToday(new Date());
  const entries = await Promise.all(
    clients.map(async (client): Promise<[string, Conditions]> => {
      if (client.archived) return [client.id, { status: "none" }];
      if (!client.address) return [client.id, { status: "address" }];
      try {
        const result = await api.POST("/api/invoices/preview", {
          body: { client_id: client.id, series_id: null, issue_date: today, concept: "Condiciones", base_cents: EXAMPLE_BASE_CENTS, vat_rate: null },
        });
        if (result.data) return [client.id, { status: "ok", text: conditionsText(result.data) }];
        const problem = problemOf(result.response, result.error); // 401 y 403 redirigen
        if (problem.code === "irpf_rate_missing") return [client.id, { status: "profile", text: problem.message }];
        if (problem.code === "profile_incomplete") return [client.id, { status: "profile", text: "Completa tu perfil para poder facturar." }];
        return [client.id, { status: "none" }];
      } catch (error) {
        unstable_rethrow(error); // una redirección (401, 403) no se traga
        return [client.id, { status: "none" }];
      }
    }),
  );
  return new Map(entries);
}
