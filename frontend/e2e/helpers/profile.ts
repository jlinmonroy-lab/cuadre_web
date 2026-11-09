// El perfil de una cuenta de E2E, por la API (SPEC-W-005 hito 5, T5-11): dejar el perfil de `gastosUser` como nació y sembrar datos sin pasar por
// el formulario.
//
// Importa porque `gastosUser` es la cuenta del worker y la comparten `perfil.spec.ts` y `gastos-*.spec.ts`: las pruebas de Gastos esperan un
// perfil VACÍO («una simplificada sin tu NIF no deduce el IVA»), así que toda prueba que escriba el perfil lo restaura al empezar y al terminar.
// Igual que `Ledger`, inicia sesión en GoTrue con la contraseña de la cuenta y habla con la API con ese token; nunca usa la service key y ni el
// token ni la clave pública se escriben en ningún sitio. Las series no se pueden borrar (solo archivar): se archivan las que no son la del año.
import type { APIRequestContext } from "@playwright/test";

import { FIRST_PASSWORD } from "./env";
import { supabaseConfig } from "./ledger";

type ListedSeries = { id: string; code: string; is_default: boolean; archived: boolean };

export class ProfileApi {
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
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para preparar el perfil (HTTP ${response.status()}).`);
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) throw new Error("GoTrue no devolvió ninguna sesión.");
    this.token = body.access_token;
    return this.token;
  }

  private async call<T>(method: "GET" | "PUT" | "PATCH" | "DELETE", route: string, data?: unknown): Promise<T | null> {
    const response = await this.request.fetch(`${this.apiUrl}${route}`, {
      method,
      headers: { Authorization: `Bearer ${await this.bearer()}` },
      ...(data === undefined ? {} : { data }),
    });
    if (!response.ok()) {
      const problem = (await response.json().catch(() => ({}))) as { code?: string };
      throw new Error(`${method} ${route} respondió ${response.status()}${problem.code ? ` (${problem.code})` : ""}.`);
    }
    return response.status() === 204 ? null : ((await response.json()) as T);
  }

  /** Guarda un perfil (los campos que no se pasen quedan vacíos: `PUT` es todo o nada). */
  async save(fields: Record<string, string | null>): Promise<void> {
    await this.call("PUT", "/api/profile", fields);
  }

  /** Deja la cuenta como nació: perfil vacío, sin logo y solo la serie del año (la predeterminada) activa. */
  async restore(): Promise<void> {
    await this.call("PUT", "/api/profile", {});
    await this.call("DELETE", "/api/profile/logo");
    const series = (await this.call<ListedSeries[]>("GET", "/api/invoice-series")) ?? [];
    const year = series.find((item) => /^\d{4}$/.test(item.code));
    if (year && (year.archived || !year.is_default)) {
      if (year.archived) await this.call("PATCH", `/api/invoice-series/${year.id}`, { archived: false });
      await this.call("PUT", `/api/invoice-series/${year.id}/default`);
    }
    for (const item of series) {
      if (item.id !== year?.id && !item.archived) await this.call("PATCH", `/api/invoice-series/${item.id}`, { archived: true });
    }
  }
}
