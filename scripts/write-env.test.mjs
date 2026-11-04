// El generador de entornos tiene que poner cada clave en su sitio y no pisar lo que ya hay: se prueba con una salida de mentira de `supabase status`.
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { collectNeedles } from "../frontend/scripts/bundle-scan.mjs";
import { buildFrontendEnv, buildRootEnv, parseStatusEnv, secretValues, writeEnvFiles } from "./write-env.mjs";

// Con forma de claves de Supabase, pero construidas en tiempo de ejecución: un literal así lo detectaría el escáner de secretos del repositorio.
const SECRET_KEY = ["sb", "secret", "s".repeat(26)].join("_");
const PUBLISHABLE_KEY = ["sb", "publishable", "p".repeat(26)].join("_");
const SERVICE_ROLE_KEY = ["jwt", "servicio", "j".repeat(30)].join(".");
const ANON_KEY = ["jwt", "anonima", "a".repeat(30)].join(".");

const STATUS_TEXT = [
  "Stopped services: [supabase_realtime_cuadre-web supabase_rest_cuadre-web]",
  `ANON_KEY="${ANON_KEY}"`,
  'API_URL="http://127.0.0.1:54321"',
  'DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"',
  'JWT_SECRET="super-secret-jwt-token-with-at-least-32-characters-long"',
  'MAILPIT_URL="http://127.0.0.1:54324"',
  `PUBLISHABLE_KEY="${PUBLISHABLE_KEY}"`,
  `SECRET_KEY="${SECRET_KEY}"`,
  `SERVICE_ROLE_KEY="${SERVICE_ROLE_KEY}"`,
  "",
].join("\r\n");

const status = parseStatusEnv(STATUS_TEXT);

function lines(text) {
  return Object.fromEntries(
    text
      .split("\n")
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => [line.slice(0, line.indexOf("=")), line.slice(line.indexOf("=") + 1)]),
  );
}

test("lee la salida de `supabase status -o env` y se salta lo que no es CLAVE=valor", () => {
  assert.equal(status.API_URL, "http://127.0.0.1:54321");
  assert.equal(status.SECRET_KEY, SECRET_KEY);
  assert.equal(status.JWT_SECRET, "super-secret-jwt-token-with-at-least-32-characters-long");
  assert.equal(Object.keys(status).length, 8);
  assert.deepEqual(parseStatusEnv("A=sin comillas\nB=\"con comillas\"\nc=minúscula\n"), { A: "sin comillas", B: "con comillas" });
});

test(".env: cada clave del backend sale de la clave de la pila que le corresponde", () => {
  const env = lines(buildRootEnv(status));
  assert.equal(env.SUPABASE_URL, status.API_URL);
  assert.equal(env.SUPABASE_SERVICE_ROLE_KEY, SECRET_KEY, "la clave de servicio es la secreta nueva, no el JWT de servicio");
  assert.equal(env.TEST_SUPABASE_ANON_KEY, PUBLISHABLE_KEY, "los tests live usan la clave publicable");
  assert.equal(env.TEST_DATABASE_ADMIN_URL, status.DB_URL);
  assert.equal(env.FRONTEND_ORIGIN, "http://localhost:3000");
  assert.equal(env.APP_ENV, "local");
});

test(".env: la API usa el rol cuadre_app y los jobs, cuadre_jobs, sobre la misma base", () => {
  const env = lines(buildRootEnv(status));
  const app = new URL(env.DATABASE_URL);
  const jobs = new URL(env.DATABASE_SERVICE_URL);
  assert.equal(app.username, "cuadre_app");
  assert.equal(jobs.username, "cuadre_jobs");
  for (const url of [app, jobs]) {
    assert.equal(url.protocol, "postgresql:");
    assert.equal(url.host, "127.0.0.1:54322");
    assert.equal(url.pathname, "/postgres");
    assert.notEqual(url.password, "postgres", "no se reutiliza la contraseña del rol postgres");
  }
});

test("frontend/.env.local: solo variables públicas y ningún secreto", () => {
  const text = buildFrontendEnv(status);
  const env = lines(text);
  assert.deepEqual(Object.keys(env), ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_API_BASE_URL"]);
  assert.equal(env.NEXT_PUBLIC_SUPABASE_ANON_KEY, PUBLISHABLE_KEY);
  assert.equal(env.NEXT_PUBLIC_SUPABASE_URL, status.API_URL);
  for (const secret of [SECRET_KEY, SERVICE_ROLE_KEY, ANON_KEY, status.JWT_SECRET, status.DB_URL]) {
    assert.ok(!text.includes(secret), "el archivo del frontend no puede contener un secreto");
  }
});

test("lo que escribe es justo lo que `check:bundle` buscará en el build", () => {
  const labels = collectNeedles(buildRootEnv(status), {}).map(({ label }) => label);
  assert.ok(labels.includes("SUPABASE_SERVICE_ROLE_KEY"));
  assert.ok(labels.includes("DATABASE_URL"));
});

test("si falta una clave de la pila, lo dice con su nombre en vez de escribir un archivo roto", () => {
  const { SECRET_KEY: _omitted, ...incomplete } = status;
  assert.throws(() => buildRootEnv(incomplete), /SECRET_KEY/);
  assert.throws(() => buildFrontendEnv({}), /API_URL, DB_URL, PUBLISHABLE_KEY, SECRET_KEY/);
});

test("enmascara en el CI todas las claves, y solo las que existen", () => {
  assert.deepEqual(secretValues(status), [SECRET_KEY, SERVICE_ROLE_KEY, ANON_KEY, status.JWT_SECRET]);
  assert.deepEqual(secretValues({ SECRET_KEY }), [SECRET_KEY]);
});

test("escribe los dos archivos y no pisa los existentes sin --force", () => {
  const dir = mkdtempSync(join(tmpdir(), "cuadre-env-"));
  const written = writeEnvFiles({ root: dir, status });
  assert.equal(written.length, 2);
  assert.ok(existsSync(join(dir, ".env")) && existsSync(join(dir, "frontend", ".env.local")));

  writeFileSync(join(dir, ".env"), "A_MANO=1\n");
  assert.throws(() => writeEnvFiles({ root: dir, status }), /No se sobrescribe sin --force/);
  assert.equal(readFileSync(join(dir, ".env"), "utf8"), "A_MANO=1\n", "un fallo no toca nada");

  writeEnvFiles({ root: dir, status, force: true });
  assert.match(readFileSync(join(dir, ".env"), "utf8"), /^# Generado por/);
});
