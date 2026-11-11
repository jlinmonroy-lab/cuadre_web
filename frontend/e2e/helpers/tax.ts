// El borrador del 303 de una cuenta de E2E, por la API (SPEC-W-008 hito 5): el ORÁCULO de `trimestres.spec.ts`.
//
// La cuenta del worker acumula facturas (no se pueden borrar, RES-03) y las comparte con otras pruebas, así que ninguna puede esperar cifras absolutas
// del trimestre en curso: lee aquí lo que dice el servidor antes y después de emitir y comprueba que la pantalla enseña lo mismo y que la diferencia es la
// esperada. Como `InvoicesApi`, inicia sesión en GoTrue con la contraseña de la cuenta y habla con la API con ese token; nunca usa la service key y ni el
// token ni la clave pública se escriben en ningún sitio. Los datos son sintéticos.
import type { APIRequestContext } from "@playwright/test";

import { FIRST_PASSWORD } from "./env";
import { supabaseConfig } from "./ledger";

export type TaxItem = { kind: "invoice" | "expense"; id: string; label: string; date: string; base_cents: number; vat_cents: number };
export type TaxBox = {
  code: string;
  label: string;
  group: string;
  measure: "base" | "vat" | null;
  amount_cents: number;
  items: TaxItem[];
  components: string[];
};
export type Tax303 = {
  year: number;
  quarter: number;
  period_start: string;
  period_end: string;
  deadline: string;
  deadline_status: string;
  boxes: TaxBox[];
  result_cents: number;
  result_kind: string;
  notes: string[];
};

export class TaxApi {
  private token: string | undefined;
  private readonly request: APIRequestContext;
  private readonly email: string;
  private readonly apiUrl: string;
  private readonly password: string;

  constructor(request: APIRequestContext, email: string, apiUrl: string, password: string = FIRST_PASSWORD) {
    this.request = request;
    this.email = email;
    this.apiUrl = apiUrl;
    this.password = password;
  }

  private async bearer(): Promise<string> {
    if (this.token) return this.token;
    const { url, anonKey } = supabaseConfig();
    const response = await this.request.post(`${url}/auth/v1/token?grant_type=password`, {
      headers: { apikey: anonKey },
      data: { email: this.email, password: this.password },
    });
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para leer el borrador del 303 (HTTP ${response.status()}).`);
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) throw new Error("GoTrue no devolvió ninguna sesión.");
    this.token = body.access_token;
    return this.token;
  }

  /** El borrador del trimestre pedido; sin parámetros, el trimestre en curso (Europe/Madrid), como la pantalla. */
  async modelo303(year?: number, quarter?: number): Promise<Tax303> {
    const query = new URLSearchParams();
    if (year !== undefined) query.set("year", String(year));
    if (quarter !== undefined) query.set("quarter", String(quarter));
    const response = await this.request.fetch(`${this.apiUrl}/api/tax/303${query.size ? `?${query}` : ""}`, {
      headers: { Authorization: `Bearer ${await this.bearer()}` },
    });
    if (!response.ok()) {
      const problem = (await response.json().catch(() => ({}))) as { code?: string };
      throw new Error(`GET /api/tax/303 respondió ${response.status()}${problem.code ? ` (${problem.code})` : ""}.`);
    }
    return (await response.json()) as Tax303;
  }
}

/** Los importes del borrador por número de casilla. */
export const amountsOf = (model: Tax303): Record<string, number> => Object.fromEntries(model.boxes.map((box) => [box.code, box.amount_cents]));

/** Lo que subió cada casilla entre dos lecturas del mismo trimestre. */
export function deltas(before: Tax303, after: Tax303): Record<string, number> {
  const a = amountsOf(before);
  return Object.fromEntries(Object.entries(amountsOf(after)).map(([code, cents]) => [code, cents - (a[code] ?? 0)]));
}
