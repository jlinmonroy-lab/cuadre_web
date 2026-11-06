import path from "node:path";

/** Puerto de la web de E2E: 3000, o `E2E_WEB_PORT` para poder probar con un `next dev` propio ocupando el 3000. */
function webPort(): number {
  const wanted = process.env.E2E_WEB_PORT ?? "3000";
  if (!/^\d{2,5}$/.test(wanted) || Number(wanted) > 65_535) throw new Error(`E2E_WEB_PORT no es un puerto válido: ${wanted}`);
  return Number(wanted);
}
export const WEB_PORT = webPort();
export const WEB_URL = `http://localhost:${WEB_PORT}`; // siempre localhost: las cookies de sesión van por host
export const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";
export const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? "http://127.0.0.1:54324";

/** Contraseña de los usuarios del seed (supabase/seed.sql): dato sintético de desarrollo, no un secreto. */
export const SEED_PASSWORD = process.env.E2E_SEED_PASSWORD ?? "cuadre-demo-2026";
/** Contraseñas inventadas para las cuentas que crean las propias pruebas (≥ 10 caracteres, T-16). */
export const FIRST_PASSWORD = "e2e-primera-clave-2026";
export const SECOND_PASSWORD = "e2e-segunda-clave-2026";

/** Sesiones guardadas por `auth.setup.ts` (gitignoradas). */
export const AUTH_DIR = path.join(__dirname, "..", ".auth");

export type RoleKey = "alicia" | "gina" | "adan";

export type Person = {
  email: string;
  name: string;
  home: string;
  roleLabel: string;
  /** Apartados de la navegación, en orden. */
  nav: string[];
  /** Los que son enlaces; el resto aparece desactivado con «Próximamente». */
  enabledNav: string[];
};

export const PEOPLE: Record<RoleKey, Person> = {
  alicia: {
    email: "alicia@example.test",
    name: "Alicia",
    home: "/inicio",
    roleLabel: "Autónomo",
    nav: ["Inicio", "Clientes", "Facturas", "Gastos", "Contabilidad mensual", "Trimestres"],
    enabledNav: ["Inicio", "Gastos"],
  },
  gina: {
    email: "gina@example.test",
    name: "Gina",
    home: "/cartera",
    roleLabel: "Gestor",
    nav: ["Cartera"],
    enabledNav: ["Cartera"],
  },
  adan: {
    email: "adan@example.test",
    name: "Adán",
    home: "/admin",
    roleLabel: "Administrador",
    nav: ["Cuentas"],
    enabledNav: [],
  },
};

export const ROLE_KEYS = Object.keys(PEOPLE) as RoleKey[];
