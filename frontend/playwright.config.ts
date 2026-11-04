// Pruebas de extremo a extremo (SPEC-W-001 §8): Chromium, Firefox y WebKit, a 390 y 1.440 px, contra `next start` (producción).
// Con la pila de Supabase en marcha (`npx supabase start`) y los puertos 3000 y 8000 libres: `npm run test:e2e`.
// Variables opcionales: E2E_PYTHON, E2E_API_URL, E2E_MAILPIT_URL, E2E_SEED_PASSWORD, E2E_REUSE_SERVER=1, E2E_DEBUG_SERVERS=1.
import { existsSync } from "node:fs";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const repoRoot = path.resolve(__dirname, "..");
const WEB = "http://localhost:3000"; // siempre localhost: las cookies de sesión van por host
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";

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
      command: `${pythonCommand()} -m uvicorn cuadre.main:app --port 8000 --app-dir backend/src --host 127.0.0.1`,
      cwd: repoRoot,
      url: `${API}/healthz`,
      reuseExistingServer: true, // la API no tiene estado propio
      timeout: 60_000,
      // El registro de peticiones de la API inunda la salida; E2E_DEBUG_SERVERS=1 lo muestra.
      stderr: process.env.E2E_DEBUG_SERVERS ? "pipe" : "ignore",
    },
    {
      // Producción, no `next dev`. No se reutiliza un servidor ya levantado (podría ser el de desarrollo) salvo con E2E_REUSE_SERVER=1.
      command: "npm run build && npm run start",
      cwd: __dirname,
      url: `${WEB}/login`,
      reuseExistingServer: REUSE,
      timeout: 240_000,
      stderr: process.env.E2E_DEBUG_SERVERS ? "pipe" : "ignore",
    },
  ],
});
