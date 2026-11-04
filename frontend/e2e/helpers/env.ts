import path from "node:path";

export const WEB_URL = "http://localhost:3000";
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
    enabledNav: ["Inicio"],
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
