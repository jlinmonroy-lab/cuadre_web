// Las facturas de una cuenta de E2E, por la API (SPEC-W-007 hito 6, T7-13): sembrar facturas sin pasar por el formulario cuando la prueba no trata de
// emitir, y leer lo emitido para comprobar la pantalla contra el servidor.
//
// Una factura emitida NO se puede borrar ni archivar (RES-03): este ayudante no limpia nada. La cuenta es la del worker y su numeración correlativa es
// un efecto esperado; ninguna prueba puede contar filas ni números absolutos y todas localizan lo suyo por un concepto único. Igual que `ClientsApi`,
// inicia sesión en GoTrue con la contraseña de la cuenta y habla con la API con ese token; nunca usa la service key y ni el token ni la clave pública
// se escriben en ningún sitio. Los datos son sintéticos.
import type { APIRequestContext } from "@playwright/test";

import { FIRST_PASSWORD } from "./env";
import { supabaseConfig } from "./ledger";

export type IssuedInvoice = {
  id: string;
  display_number: string;
  kind: "standard" | "rectifying";
  client: { id: string; name: string };
  concept: string;
  base_cents: number;
  vat_cents: number;
  irpf_cents: number;
  total_cents: number;
  paid_at: string | null;
  pdf_status: "ready" | "pending";
};

export type InvoiceDraft = {
  client_id: string;
  concept: string;
  base_cents: number;
  issue_date?: string;
  series_id?: string | null;
  vat_rate?: string | null;
};

/** Hoy en Madrid como `AAAA-MM-DD`: el servidor valida con el reloj de Madrid y exige una fecha. */
export function madridToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export class InvoicesApi {
  private token: string | undefined;
  private readonly request: APIRequestContext;
  private readonly email: string;
  private readonly apiUrl: string;

  constructor(request: APIRequestContext, email: string, apiUrl: string) {
    this.request = request;
    this.email = email;
    this.apiUrl = apiUrl;
  }

  private async bearer(): Promise<string> {
    if (this.token) return this.token;
    const { url, anonKey } = supabaseConfig();
    const response = await this.request.post(`${url}/auth/v1/token?grant_type=password`, {
      headers: { apikey: anonKey },
      data: { email: this.email, password: FIRST_PASSWORD },
    });
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para preparar las facturas (HTTP ${response.status()}).`);
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) throw new Error("GoTrue no devolvió ninguna sesión.");
    this.token = body.access_token;
    return this.token;
  }

  private async call<T>(method: "GET" | "POST", route: string, data?: unknown): Promise<T> {
    const response = await this.request.fetch(`${this.apiUrl}${route}`, {
      method,
      headers: { Authorization: `Bearer ${await this.bearer()}` },
      ...(data === undefined ? {} : { data }),
    });
    if (!response.ok()) {
      const problem = (await response.json().catch(() => ({}))) as { code?: string };
      // Ni la ruta con su id ni el cuerpo (concepto, importes) van al mensaje.
      throw new Error(`${method} ${(route.split("?")[0] ?? route).replace(/[0-9a-f-]{36}/g, ":id")} respondió ${response.status()}${problem.code ? ` (${problem.code})` : ""}.`);
    }
    return (await response.json()) as T;
  }

  /** Emite una factura como la emitiría el formulario (la API valida igual). */
  async issue(draft: InvoiceDraft): Promise<IssuedInvoice> {
    return this.call<IssuedInvoice>("POST", "/api/invoices", { series_id: null, vat_rate: null, issue_date: madridToday(), ...draft });
  }

  /** Emite una rectificativa de `invoiceId` con la base corregida en céntimos. */
  async rectify(invoiceId: string, correctedBaseCents: number, reason = "Corrección de prueba", issueDate?: string): Promise<IssuedInvoice> {
    return this.call<IssuedInvoice>("POST", `/api/invoices/${invoiceId}/rectifications`, {
      reason,
      corrected_base_cents: correctedBaseCents,
      issue_date: issueDate ?? madridToday(),
    });
  }

  /** Crea una serie de facturación (no predeterminada): una serie nueva no tiene facturas, así que admite una factura con fecha de un mes pasado. */
  async createSeries(code: string): Promise<{ id: string }> {
    return this.call<{ id: string }>("POST", "/api/invoice-series", { code, make_default: false });
  }

  /** Las facturas del año actual de la cuenta (la más reciente primero). */
  async list(): Promise<IssuedInvoice[]> {
    return this.call<IssuedInvoice[]>("GET", "/api/invoices");
  }

  /** La factura con ese concepto (único por prueba), o `undefined`. */
  async byConcept(concept: string): Promise<IssuedInvoice | undefined> {
    return (await this.list()).find((invoice) => invoice.concept === concept);
  }
}
