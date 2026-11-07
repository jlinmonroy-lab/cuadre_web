// El libro de gastos de una cuenta de E2E, por la API (SPEC-W-003 hito 5): sembrar gastos sin pasar cincuenta veces por el formulario y
// dejar la cuenta sin gastos vivos al terminar cada prueba.
//
// Lo segundo es lo importante: varias pruebas comparten la cuenta de su worker (`gastosUser`) y registran la misma factura de ejemplo, y un
// gasto vivo de una haría fallar «No está registrada ya» en otra. Crear una cuenta por prueba no sirve (cada una envía un correo y la pila
// local limita a 100 por hora). Se inicia sesión con la contraseña de la cuenta contra GoTrue, como haría la propia web, y se habla con la
// API con ese token; nunca se usa la service key y ni el token ni la clave pública se escriben en ningún sitio.
import { readFileSync } from "node:fs";
import path from "node:path";

import type { APIRequestContext } from "@playwright/test";

import { FIRST_PASSWORD } from "./env";

type SupabaseConfig = { url: string; anonKey: string };

/** Lee `KEY=valor` de un archivo de entorno; un archivo que no existe es un archivo vacío. */
function readEnvFile(file: string): Record<string, string> {
  let text = "";
  try {
    text = readFileSync(file, "utf8");
  } catch {
    return {};
  }
  const values: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (match?.[1] && !line.trimStart().startsWith("#")) values[match[1]] = (match[2] ?? "").replace(/^(["'])(.*)\1$/, "$2");
  }
  return values;
}

/**
 * Dónde está GoTrue y su clave pública: `E2E_SUPABASE_URL` y `E2E_SUPABASE_ANON_KEY`, o lo que `npm run env:local` dejó en
 * `frontend/.env.local` (también en el CI). La clave pública no es un secreto, pero tampoco se imprime.
 */
function supabaseConfig(): SupabaseConfig {
  const file = readEnvFile(path.join(__dirname, "..", "..", ".env.local"));
  const url = process.env.E2E_SUPABASE_URL ?? file["NEXT_PUBLIC_SUPABASE_URL"];
  const anonKey = process.env.E2E_SUPABASE_ANON_KEY ?? file["NEXT_PUBLIC_SUPABASE_ANON_KEY"];
  if (!url || !anonKey) {
    throw new Error(
      "Faltan la URL y la clave pública de Supabase para las pruebas de gastos: ejecuta `npm run env:local` (crea frontend/.env.local) " +
        "o define E2E_SUPABASE_URL y E2E_SUPABASE_ANON_KEY.",
    );
  }
  return { url: url.replace(/\/$/, ""), anonKey };
}

/** Lo que las pruebas necesitan de un gasto de la lista (el resto de campos no importa). */
type ListedExpense = { id: string };
type ExpensePage = { items: ListedExpense[]; next_cursor: string | null };

/** Prefijo y número de los gastos sembrados: el 1 es el más antiguo y el último el más reciente. */
export const SEEDED_CONCEPT = "Gasto de prueba";
export const seededConcept = (index: number): string => `${SEEDED_CONCEPT} ${String(index).padStart(2, "0")}`;

/** Día del gasto sembrado número `index` (1 = 1 de enero de 2026): todos pasados y cada uno de un día distinto, así el orden es el de `index`. */
function seededDay(index: number): string {
  return new Date(Date.UTC(2026, 0, index)).toISOString().slice(0, 10);
}

export class Ledger {
  private token: string | undefined;
  private readonly request: APIRequestContext;
  private readonly email: string;
  private readonly apiUrl: string;

  constructor(request: APIRequestContext, email: string, apiUrl: string) {
    this.request = request;
    this.email = email;
    this.apiUrl = apiUrl;
  }

  /** Inicia sesión una vez por instancia (contraseña de las cuentas que crea el propio E2E). */
  private async bearer(): Promise<string> {
    if (this.token) return this.token;
    const { url, anonKey } = supabaseConfig();
    const response = await this.request.post(`${url}/auth/v1/token?grant_type=password`, {
      headers: { apikey: anonKey },
      data: { email: this.email, password: FIRST_PASSWORD },
    });
    if (!response.ok()) throw new Error(`No se pudo iniciar sesión para preparar los gastos (HTTP ${response.status()}).`);
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
      throw new Error(`${method} ${route.split("?")[0]} respondió ${response.status()}${problem.code ? ` (${problem.code})` : ""}.`);
    }
    return (await response.json()) as T;
  }

  /** Crea `count` gastos sin factura («Gasto de prueba 01»…), uno por día desde el 1 de enero de 2026; el último es el más reciente. */
  async seed(count: number): Promise<void> {
    for (let index = 1; index <= count; index += 1) {
      await this.call("POST", "/api/expenses", {
        expense_date: seededDay(index),
        concept: seededConcept(index),
        category: "other",
        amount_cents: 1000 + index,
      });
    }
  }

  /** Anula todos los gastos vivos de la cuenta (los anulados no cuentan para duplicados ni salen en la lista). */
  async voidAll(): Promise<void> {
    const ids: string[] = [];
    let cursor: string | null = null;
    do {
      const page: ExpensePage = await this.call("GET", `/api/expenses${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`);
      ids.push(...page.items.map((expense) => expense.id));
      cursor = page.next_cursor;
    } while (cursor);
    for (const id of ids) await this.call("POST", `/api/expenses/${id}/void`);
  }
}
