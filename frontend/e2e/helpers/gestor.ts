// El acceso del gestor de una cuenta de E2E, por la API (SPEC-W-010 hito 5, T10-12): invitar, aceptar, rechazar y revocar sin pasar por la interfaz cuando la
// prueba no trata de eso, y dejar la cuenta sin accesos abiertos al terminar.
//
// Importa porque la gestora de los datos sembrados (Gina) es COMPARTIDA por todos los workers y proyectos: un vínculo que se quedase abierto aparecería en la
// cartera de las demás pruebas, y la cuenta de cada worker admite como mucho 5 invitaciones abiertas. Igual que `InvoicesApi`, inicia sesión en GoTrue con la
// contraseña de la cuenta (la de las cuentas que crea el propio E2E, o la del seed para Gina y Gus) y habla con la API con ese token; nunca usa la service key y
// ni el token ni la clave pública se escriben en ningún sitio. Los datos son sintéticos.
import type { APIRequestContext } from "@playwright/test";

import { supabaseConfig } from "./ledger";

export type Access = {
  id: string;
  gestor_email: string;
  status: "pending" | "active" | "revoked" | "declined" | "expired";
  invited_at: string;
  expires_at: string;
};
export type InvitedAccess = Access & { email_sent: boolean };
export type Invitation = { id: string; owner_name: string; invited_at: string; expires_at: string };
export type PortfolioEntry = { id: string; name: string; email: string; pending_count: number };

export class GestorApi {
  private token: string | undefined;
  private readonly request: APIRequestContext;
  private readonly email: string;
  private readonly password: string;
  private readonly apiUrl: string;

  constructor(request: APIRequestContext, email: string, password: string, apiUrl: string) {
    this.request = request;
    this.email = email;
    this.password = password;
    this.apiUrl = apiUrl;
  }

  private async bearer(): Promise<string> {
    if (this.token) return this.token;
    const { url, anonKey } = supabaseConfig();
    const response = await this.request.post(`${url}/auth/v1/token?grant_type=password`, {
      headers: { apikey: anonKey },
      data: { email: this.email, password: this.password },
    });
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para preparar el acceso del gestor (HTTP ${response.status()}).`);
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) throw new Error("GoTrue no devolvió ninguna sesión.");
    this.token = body.access_token;
    return this.token;
  }

  private async call<T>(method: "GET" | "POST", route: string, data?: unknown): Promise<T | null> {
    const response = await this.request.fetch(`${this.apiUrl}${route}`, {
      method,
      headers: { Authorization: `Bearer ${await this.bearer()}` },
      ...(data === undefined ? {} : { data }),
    });
    if (!response.ok()) {
      const problem = (await response.json().catch(() => ({}))) as { code?: string };
      // Ni la ruta con su id ni el cuerpo (el correo del gestor) van al mensaje.
      throw new Error(`${method} ${(route.split("?")[0] ?? route).replace(/[0-9a-f-]{36}/g, ":id")} respondió ${response.status()}${problem.code ? ` (${problem.code})` : ""}.`);
    }
    return response.status() === 204 ? null : ((await response.json()) as T);
  }

  // --- Como autónomo ---------------------------------------------------------------------------------------------------------------

  /** Invita a un gestor por su correo (la API valida igual que el formulario). */
  async invite(email: string): Promise<InvitedAccess> {
    return (await this.call<InvitedAccess>("POST", "/api/gestor/accesos", { email }))!;
  }

  async accesses(): Promise<Access[]> {
    return (await this.call<Access[]>("GET", "/api/gestor/accesos")) ?? [];
  }

  async revoke(accessId: string): Promise<void> {
    await this.call("POST", `/api/gestor/accesos/${accessId}/revocar`);
  }

  /** Revoca todo lo que esté abierto (pendiente o activo): deja la cuenta sin vínculos y sin invitaciones que cuenten para el límite. */
  async revokeOpen(): Promise<void> {
    for (const access of await this.accesses()) {
      if (access.status === "pending" || access.status === "active") await this.revoke(access.id);
    }
  }

  // --- Como gestor -----------------------------------------------------------------------------------------------------------------

  async invitations(): Promise<Invitation[]> {
    return (await this.call<Invitation[]>("GET", "/api/gestor/invitaciones")) ?? [];
  }

  async portfolio(): Promise<PortfolioEntry[]> {
    return (await this.call<PortfolioEntry[]>("GET", "/api/gestor/cartera")) ?? [];
  }

  /** Acepta la invitación de quien se llama `ownerName` (el nombre es único por worker) y devuelve el id del autónomo en la cartera. */
  async acceptFrom(ownerName: string): Promise<string> {
    const invitation = (await this.invitations()).find((item) => item.owner_name === ownerName);
    if (!invitation) throw new Error("No hay ninguna invitación de esa cuenta.");
    await this.call("POST", `/api/gestor/invitaciones/${invitation.id}/aceptar`);
    const entry = (await this.portfolio()).find((item) => item.name === ownerName);
    if (!entry) throw new Error("La cuenta no aparece en la cartera tras aceptar.");
    return entry.id;
  }

  /** Lee `times` veces los clientes de un autónomo con vínculo: cada lectura deja una entrada en su registro de actividad (para llenar páginas). */
  async touch(ownerId: string, times: number): Promise<void> {
    for (let n = 0; n < times; n += 1) await this.call("GET", `/api/gestor/autonomos/${ownerId}/clientes`);
  }

  /** Los pendientes de la cuenta `ownerName` en la cartera de este gestor. */
  async pendingOf(ownerName: string): Promise<number> {
    const entry = (await this.portfolio()).find((item) => item.name === ownerName);
    if (!entry) throw new Error("La cuenta no aparece en la cartera.");
    return entry.pending_count;
  }
}
