// Pruebas de extremo a extremo (SPEC-W-001 §8): Chromium, Firefox y WebKit, a 390 y 1.440 px, contra `next start` (producción).
// Con la pila de Supabase en marcha (`npx supabase start`) y los puertos 3000, 8000 y 8765 libres: `npm run test:e2e`.
// Variables opcionales: E2E_PYTHON, E2E_API_URL, E2E_MAILPIT_URL, E2E_SEED_PASSWORD, E2E_WEB_PORT (si el 3000 está ocupado),
// E2E_AGENTS_PORT (si lo está el 8765), E2E_SUPABASE_URL y E2E_SUPABASE_ANON_KEY (si no se leen de `frontend/.env.local`),
// E2E_REUSE_SERVER=1, E2E_DEBUG_SERVERS=1.
//
// Tres servidores: la API, la web (producción) y un servidor de agentes de E2E (`backend/tests/agents/e2e_server.py`). La API lo usa como
// `AGENTS_BASE_URL`, así que lee con `HttpAgentsClient` y no con el simulado cíclico, cuyo orden global no sirve con proyectos en paralelo:
// cada prueba elige qué lee el agente con un marcador dentro del archivo que sube (SPEC-W-002 B.7).
import { existsSync } from "node:fs";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

import { AGENTS_PORT, API_URL as API, WEB_PORT, WEB_URL as WEB } from "./e2e/helpers/env";

const repoRoot = path.resolve(__dirname, "..");
const AGENTS_URL = `http://127.0.0.1:${AGENTS_PORT}`;
/** Clave inventada que comparten la API y el servidor de agentes de E2E: no protege nada, es un dato de prueba. */
const AGENTS_KEY = "e2e-agents-key-solo-para-pruebas";

/** Intérprete de Python: `E2E_PYTHON`, si no el del `.venv` del repositorio y, si no, el `python` del PATH (CI con el entorno activado). */
function pythonCommand(): string {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON;
  const venv =
    process.platform === "win32"
      ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
      : path.join(repoRoot, ".venv", "bin", "python");
  return existsSync(venv) ? `"${venv}"` : "python";
}

const engines = [
  { name: "chromium", device: devices["Desktop Chrome"] },
  { name: "firefox", device: devices["Desktop Firefox"] },
  { name: "webkit", device: devices["Desktop Safari"] },
] as const;

// Solo `viewport` (sin `isMobile`, que Firefox no admite): lo que importa es el ancho para las media queries.
const sizes = [
  { name: "390", viewport: { width: 390, height: 844 } },
  { name: "1440", viewport: { width: 1440, height: 900 } },
] as const;

const REUSE = Boolean(process.env.E2E_REUSE_SERVER);

export default defineConfig({
  testDir: "./e2e",
  outputDir: "test-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 4,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: WEB,
    locale: "es-ES",
    timezoneId: "Europe/Madrid",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: engines.flatMap(({ name, device }) => [
    // Un inicio de sesión por rol y por motor, guardado en e2e/.auth/ (gitignorado) para las pruebas que solo necesitan «estar dentro».
    { name: `setup-${name}`, testMatch: /auth\.setup\.ts/, use: { ...device } },
    ...sizes.map((size) => ({
      name: `${name}-${size.name}`,
      dependencies: [`setup-${name}`],
      testIgnore: name === "chromium" && size.name === "1440" ? [/auth\.setup\.ts/] : [/auth\.setup\.ts/, /bundle\.spec\.ts/],
      use: { ...device, viewport: size.viewport },
    })),
  ]),
  webServer: [
    {
      // Su único estado es cuántas veces ha leído cada documento (para `a>b`): se puede reutilizar.
      command: `${pythonCommand()} -m tests.agents.e2e_server --port ${AGENTS_PORT}`,
      cwd: path.join(repoRoot, "backend"),
      url: `${AGENTS_URL}/healthz`,
      reuseExistingServer: true,
      timeout: 30_000,
      env: { AGENTS_API_KEY: AGENTS_KEY },
      stderr: process.env.E2E_DEBUG_SERVERS ? "pipe" : "ignore",
    },
    {
      command: `${pythonCommand()} -m uvicorn cuadre.main:app --port 8000 --app-dir backend/src --host 127.0.0.1`,
      cwd: repoRoot,
      url: `${API}/healthz`,
      // Ya no se reutiliza (salvo con E2E_REUSE_SERVER=1): una API levantada a mano leería con el simulado cíclico y las pruebas de Gastos
      // fallarían sin explicación. Quien la reutilice debe arrancarla con AGENTS_BASE_URL y AGENTS_API_KEY de este archivo.
      reuseExistingServer: REUSE,
      timeout: 60_000,
      env: { AGENTS_BASE_URL: AGENTS_URL, AGENTS_API_KEY: AGENTS_KEY },
      // El registro de peticiones de la API inunda la salida; E2E_DEBUG_SERVERS=1 lo muestra.
      stderr: process.env.E2E_DEBUG_SERVERS ? "pipe" : "ignore",
    },
    {
      // Producción, no `next dev`. No se reutiliza un servidor ya levantado (podría ser el de desarrollo) salvo con E2E_REUSE_SERVER=1.
      command: `npm run build && npm run start -- -p ${WEB_PORT}`,
      cwd: __dirname,
      url: `${WEB}/login`,
      reuseExistingServer: REUSE,
      timeout: 240_000,
      stderr: process.env.E2E_DEBUG_SERVERS ? "pipe" : "ignore",
    },
  ],
});
