// Genera `.env` (backend y tests) y `frontend/.env.local` (solo NEXT_PUBLIC_*) a partir de la pila local de Supabase en marcha.
// `npm run env:local` en desarrollo; `node scripts/write-env.mjs --ci` en el CI (también enmascara las claves en el registro).
// Se niega a sobrescribir archivos que ya existen salvo con `--force`. Los valores son los de la pila de desarrollo: no sirven fuera de ella.
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const REQUIRED = ["API_URL", "DB_URL", "PUBLISHABLE_KEY", "SECRET_KEY"];

// La fija supabase/seed.sql para cuadre_app y cuadre_jobs: es un dato de desarrollo, no un secreto.
const APP_ROLE_PASSWORD = "cuadre-dev-only";

/** Convierte la salida de `supabase status -o env` (`CLAVE="valor"`) en un objeto. */
export function parseStatusEnv(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const match = /^([A-Z][A-Z0-9_]*)=(?:"(.*)"|(.*))$/.exec(line.trim());
    if (match) values[match[1]] = match[2] ?? match[3] ?? "";
  }
  return values;
}

function requireStatus(status) {
  const missing = REQUIRED.filter((name) => !status[name]);
  if (missing.length > 0) throw new Error(`Falta ${missing.join(", ")} en la salida de «supabase status -o env». ¿Está en marcha la pila?`);
}

/** Misma conexión que `DB_URL` pero con otro rol de login. */
function withRole(dbUrl, role, password) {
  const url = new URL(dbUrl);
  url.username = role;
  url.password = password;
  return url.toString();
}

/** `.env` de la raíz: lo leen la API, los tests y la CLI. Nunca llega al frontend (T-15). */
export function buildRootEnv(status) {
  requireStatus(status);
  return [
    "# Generado por `npm run env:local` a partir de la pila local de Supabase. Ignorado por git (RES-07); no sirve fuera de la pila de desarrollo.",
    "APP_ENV=local",
    "LOG_LEVEL=INFO",
    "FRONTEND_ORIGIN=http://localhost:3000",
    "",
    `SUPABASE_URL=${status.API_URL}`,
    `SUPABASE_SERVICE_ROLE_KEY=${status.SECRET_KEY}`,
    "# ADMIN_PASSWORD: solo para `python -m cuadre.cli create-admin`; añádela tú si la necesitas.",
    "",
    `DATABASE_URL=${withRole(status.DB_URL, "cuadre_app", APP_ROLE_PASSWORD)}`,
    `DATABASE_SERVICE_URL=${withRole(status.DB_URL, "cuadre_jobs", APP_ROLE_PASSWORD)}`,
    "",
    "# Solo para los tests",
    `TEST_DATABASE_ADMIN_URL=${status.DB_URL}`,
    `TEST_SUPABASE_ANON_KEY=${status.PUBLISHABLE_KEY}`,
    "",
  ].join("\n");
}

/** `frontend/.env.local`: solo lo público. La API de cuadre-web escucha en el 8000 (ver README). */
export function buildFrontendEnv(status) {
  requireStatus(status);
  return [
    "# Solo variables públicas (NEXT_PUBLIC_*). Generado por `npm run env:local`. Este archivo NO se versiona (RES-07).",
    `NEXT_PUBLIC_SUPABASE_URL=${status.API_URL}`,
    `NEXT_PUBLIC_SUPABASE_ANON_KEY=${status.PUBLISHABLE_KEY}`,
    "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000",
    "",
  ].join("\n");
}

/** Valores que el CI debe enmascarar en su registro. */
export function secretValues(status) {
  return [status.SECRET_KEY, status.SERVICE_ROLE_KEY, status.ANON_KEY, status.JWT_SECRET].filter(Boolean);
}

/** Escribe los dos archivos bajo `root`. Devuelve las rutas escritas; lanza si alguna ya existe y no hay `force`. */
export function writeEnvFiles({ root, status, force = false }) {
  const targets = [
    [resolve(root, ".env"), buildRootEnv(status)],
    [resolve(root, "frontend", ".env.local"), buildFrontendEnv(status)],
  ];
  const existing = targets.map(([path]) => path).filter((path) => existsSync(path));
  if (existing.length > 0 && !force) {
    throw new Error(`Ya existe: ${existing.join(", ")}. No se sobrescribe sin --force.`);
  }
  for (const [path, content] of targets) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content, "utf8");
  }
  return targets.map(([path]) => path);
}

function main(argv) {
  const flags = new Set(argv);
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const outArg = argv.indexOf("--out"); // carpeta de destino (pruebas); por defecto, la raíz del repositorio
  const out = outArg >= 0 ? resolve(argv[outArg + 1]) : repoRoot;

  const result = spawnSync("npx", ["supabase", "status", "-o", "env"], { cwd: repoRoot, encoding: "utf8", shell: true });
  if (result.status !== 0) {
    console.error("No se pudo leer `supabase status`. ¿Está en marcha `npx supabase start`?");
    return 1;
  }
  const status = parseStatusEnv(result.stdout);
  try {
    if (flags.has("--ci")) for (const value of secretValues(status)) console.log(`::add-mask::${value}`);
    for (const path of writeEnvFiles({ root: out, status, force: flags.has("--force") })) console.log(`escrito ${path}`);
  } catch (error) {
    console.error(error.message);
    return 1;
  }
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exit(main(process.argv.slice(2)));
