// Los clientes de una cuenta de E2E, por la API (SPEC-W-006 hito 5, T6-10): sembrar clientes sin pasar por el formulario y dejar la cuenta sin
// clientes activos al empezar y al terminar cada prueba.
//
// Un cliente no se puede borrar (solo archivar), y la cuenta es la del worker (`gastosUser`): ninguna prueba debe depender de lo que dejó otra,
// ni de un NIF que siga activo (el NIF es único entre los activos de cada persona). Igual que `Ledger` y `ProfileApi`, inicia sesión en GoTrue con
// la contraseña de la cuenta y habla con la API con ese token; nunca usa la service key y ni el token ni la clave pública se escriben en ningún
// sitio. Los datos son sintéticos.
import type { APIRequestContext } from "@playwright/test";

import { FIRST_PASSWORD } from "./env";
import { supabaseConfig } from "./ledger";

export type ClientInput = {
  name: string;
  kind: "business" | "individual";
  country: string;
  tax_id?: string | null;
  address?: string | null;
};

export type ListedClient = { id: string; name: string; scope: string; vies_status: string; tax_id: string | null; archived: boolean };

export class ClientsApi {
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
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para preparar los clientes (HTTP ${response.status()}).`);
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) throw new Error("GoTrue no devolvió ninguna sesión.");
    this.token = body.access_token;
    return this.token;
  }

  private async call<T>(method: "GET" | "POST" | "PUT", route: string, data?: unknown): Promise<T> {
    const response = await this.request.fetch(`${this.apiUrl}${route}`, {
      method,
      headers: { Authorization: `Bearer ${await this.bearer()}` },
      ...(data === undefined ? {} : { data }),
    });
    if (!response.ok()) {
      const problem = (await response.json().catch(() => ({}))) as { code?: string };
      // Ni la ruta con su id ni el cuerpo (nombre, NIF) van al mensaje.
      throw new Error(`${method} ${(route.split("?")[0] ?? route).replace(/[0-9a-f-]{36}/g, ":id")} respondió ${response.status()}${problem.code ? ` (${problem.code})` : ""}.`);
    }
    return (await response.json()) as T;
  }

  /** Crea un cliente (la API valida igual que el formulario). */
  async create(input: ClientInput): Promise<ListedClient> {
    return this.call<ListedClient>("POST", "/api/clients", { tax_id: null, address: null, ...input });
  }

  async list(includeArchived = false): Promise<ListedClient[]> {
    return this.call<ListedClient[]>("GET", `/api/clients?include_archived=${includeArchived}`);
  }

  /** Archiva un cliente (para sembrar uno ya archivado). */
  async archive(id: string): Promise<void> {
    await this.call("PUT", `/api/clients/${id}/archived`, { archived: true });
  }

  /** Archiva todos los clientes activos de la cuenta (los archivados no cuentan para el NIF único ni salen en la lista). */
  async archiveAll(): Promise<void> {
    for (const client of await this.list(false)) await this.call("PUT", `/api/clients/${client.id}/archived`, { archived: true });
  }
}
