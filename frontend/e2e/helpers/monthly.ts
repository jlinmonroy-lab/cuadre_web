// La contabilidad mensual de una cuenta de E2E, por la API (SPEC-W-012 hito 5): el ORÁCULO de `mensual.spec.ts` y el modo de cerrar un mes solo para esa cuenta.
//
// La cuenta del worker acumula facturas (no se pueden borrar, RES-03) y las comparte con otras pruebas, así que ninguna puede esperar cifras absolutas: lee aquí
// lo que dice el servidor y comprueba que la pantalla enseña lo mismo. Como `TaxApi`, inicia sesión en GoTrue con la contraseña de la cuenta y habla con la API
// con ese token; nunca usa la clave de servicio y ni el token ni la clave pública se escriben en ningún sitio. Los datos son sintéticos.
//
// El cierre lo hace el job. La ruta interna del planificador recorre TODAS las cuentas de la base, y la de pruebas acumula miles, así que aquí se ejecuta la CLI
// (`python -m cuadre.cli close-month`) limitada a una sola cuenta, con el mismo intérprete que el servidor de E2E. La CLI lee su configuración del `.env` del
// repositorio, igual que la API.
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";

import type { APIRequestContext } from "@playwright/test";

import { FIRST_PASSWORD } from "./env";
import { supabaseConfig } from "./ledger";

const run = promisify(execFile);
const repoRoot = path.resolve(__dirname, "..", "..", "..");

export type ClientTotals = { client_id: string; name: string; scope: "national" | "eu" | "non_eu"; base_cents: number; invoice_count: number };
export type MonthRow = {
  month: number;
  status: "closed" | "in_progress" | "pending";
  invoice_count: number;
  national_cents: number;
  eu_cents: number;
  non_eu_cents: number;
  total_cents: number;
  expenses_cents: number;
  result_cents: number;
  ytd_cents: number;
  revision: number | null;
  closed_at: string | null;
};
export type MonthlyClosings = {
  year: number;
  months: MonthRow[];
  totals: { invoice_count: number; national_cents: number; eu_cents: number; non_eu_cents: number; total_cents: number; expenses_cents: number };
};
export type MonthlyClosing = MonthRow & { year: number; by_client: ClientTotals[] };
export type Scope = "national" | "eu" | "non_eu";
export type MonthlyReport = MonthlyClosing & {
  comparison: {
    previous_year: number;
    previous_month: number;
    previous_status: MonthRow["status"];
    total_cents: number;
    expenses_cents: number;
    result_cents: number;
    total_delta_cents: number;
    expenses_delta_cents: number;
    result_delta_cents: number;
    total_variation_bp: number | null;
    expenses_variation_bp: number | null;
  } | null;
  scopes: { scope: Scope; base_cents: number; share_bp: number | null }[];
  expenses_by_category: { category: string; label: string; expenses_cents: number; expense_count: number }[];
  expenses_by_category_total_cents: number;
  expenses_note: string | null;
  trend: { year: number; month: number; status: MonthRow["status"]; total_cents: number; expenses_cents: number; result_cents: number }[];
  quarter: number;
  quarter_year: number;
};

/** El intérprete de Python que usa el servidor de E2E: `E2E_PYTHON`, si no el del `.venv` del repositorio y, si no, el `python` del PATH. */
function python(): string {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON.replace(/^"|"$/g, "");
  const venv = process.platform === "win32" ? path.join(repoRoot, ".venv", "Scripts", "python.exe") : path.join(repoRoot, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python";
}

export const monthKey = (year: number, month: number): string => `${year}-${String(month).padStart(2, "0")}`;

/** El mes anterior al de hoy en Madrid (el último que ya ha terminado). */
export function previousMonth(todayIso: string): { year: number; month: number } {
  const year = Number(todayIso.slice(0, 4));
  const month = Number(todayIso.slice(5, 7));
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

export class MonthlyApi {
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
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para leer la contabilidad mensual (HTTP ${response.status()}).`);
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) throw new Error("GoTrue no devolvió ninguna sesión.");
    this.token = body.access_token;
    return this.token;
  }

  private async get<T>(route: string): Promise<T> {
    const response = await this.request.fetch(`${this.apiUrl}${route}`, { method: "GET", headers: { Authorization: `Bearer ${await this.bearer()}` } });
    if (!response.ok()) throw new Error(`GET ${route} respondió ${response.status()}.`);
    return (await response.json()) as T;
  }

  /** El id de la cuenta (para limitar el cierre a ella). */
  async userId(): Promise<string> {
    return (await this.get<{ id: string }>("/api/me")).id;
  }

  async year(year: number): Promise<MonthlyClosings> {
    return this.get<MonthlyClosings>(`/api/monthly-closings?year=${year}`);
  }

  async month(year: number, month: number): Promise<MonthlyClosing> {
    return this.get<MonthlyClosing>(`/api/monthly-closings/${year}/${month}`);
  }

  /** El reporte de un mes (SPEC-W-013): el oráculo de `reporte.spec.ts`. */
  async report(year: number, month: number): Promise<MonthlyReport> {
    return this.get<MonthlyReport>(`/api/monthly-report/${year}/${month}`);
  }

  /** Cierra (o recalcula) un mes de esta cuenta con la CLI del job. Imprime solo contadores. */
  async close(year: number, month: number): Promise<string> {
    const { stdout } = await run(python(), ["-m", "cuadre.cli", "close-month", "--month", monthKey(year, month), "--user", await this.userId()], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONPATH: path.join(repoRoot, "backend", "src") },
      timeout: 60_000,
    });
    return stdout.trim();
  }
}
