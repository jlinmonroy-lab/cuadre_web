// El comprobador del bundle tiene que detectar fugas de verdad: se prueba con ficheros de mentira.
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { STATIC_NEEDLES, collectNeedles, findLeaks } from "./bundle-scan.mjs";

function fixture(files) {
  const dir = mkdtempSync(join(tmpdir(), "cuadre-bundle-"));
  for (const [name, content] of Object.entries(files)) {
    const path = join(dir, name);
    mkdirSync(join(path, ".."), { recursive: true });
    writeFileSync(path, content);
  }
  return dir;
}

const SECRET = "valor-secreto-de-prueba-0123456789";
// Con forma de clave secreta de Supabase, pero construida en tiempo de ejecución: un literal así en el repositorio lo detectaría el
// propio escáner de secretos (backend/tests/rules/test_no_secrets_tracked.py).
const FAKE_KEY = ["sb", "secret", "a".repeat(26)].join("_");

test("detecta las cadenas fijas prohibidas, en cualquier fichero de texto", () => {
  const dir = fixture({
    "static/chunks/a.js": 'const k = "SUPABASE_SERVICE_ROLE_KEY";',
    "server/b.js": `x = '${FAKE_KEY}';`,
    "server/ok.js": "const url = process.env.NEXT_PUBLIC_SUPABASE_URL;",
  });
  const hits = findLeaks(dir, STATIC_NEEDLES);
  assert.deepEqual(
    hits.map((hit) => hit.file).sort(),
    ["server/b.js", "static/chunks/a.js"],
  );
});

test("el prefijo suelto «sb_secret_» (la comprobación de supabase-js) no es una fuga; una clave entera sí", () => {
  const dir = fixture({
    "server/lib.js": 'let isKey = (e) => e.startsWith("sb_publishable_") || e.startsWith("sb_secret_");',
    "server/leak.js": `const key = "${FAKE_KEY}";`,
  });
  assert.deepEqual(findLeaks(dir, STATIC_NEEDLES).map((hit) => hit.file), ["server/leak.js"]);
});

test("detecta el VALOR de un secreto del entorno aunque no aparezca su nombre", () => {
  const dir = fixture({ "static/c.js": `fetch("https://x.test/?k=${SECRET}")`, "static/d.js": "nada" });
  const hits = findLeaks(dir, [{ label: "SUPABASE_SERVICE_ROLE_KEY", value: SECRET }]);
  assert.deepEqual(hits, [{ file: "static/c.js", label: "SUPABASE_SERVICE_ROLE_KEY" }]);
});

test("no mira la caché de compilación", () => {
  const dir = fixture({ "cache/webpack/x.js": `"${SECRET}"`, "server/app.js": "limpio" });
  assert.deepEqual(findLeaks(dir, [{ label: "S", value: SECRET }]), []);
});

test("una carpeta llamada «cache» más abajo en el árbol SÍ se revisa", () => {
  const dir = fixture({ "server/app/cache/page.js": `"${SECRET}"` });
  assert.deepEqual(findLeaks(dir, [{ label: "S", value: SECRET }]), [{ file: "server/app/cache/page.js", label: "S" }]);
});

test("sin fugas, no hay resultados", () => {
  const dir = fixture({ "a.js": "hola", "b/c.html": "<p>hola</p>" });
  assert.deepEqual(findLeaks(dir, [{ label: "S", value: SECRET }]), []);
});

test("los valores del .env solo cuentan si parecen secretos reales (no vacíos, cortos ni marcadores)", () => {
  const env = [
    "# comentario",
    `SUPABASE_SERVICE_ROLE_KEY=${SECRET}`,
    "ADMIN_PASSWORD=<elige-una>",
    "MCP_TOKEN_SECRET=corto",
    "INTERNAL_JOBS_SECRET=",
    `DATABASE_SERVICE_URL=postgresql://cuadre_jobs:${SECRET}@127.0.0.1:54322/postgres   # comentario`,
    "FRONTEND_ORIGIN=http://localhost:3000",
  ].join("\n");
  const needles = collectNeedles(env, {});
  assert.deepEqual(needles.map((needle) => needle.label).sort(), ["DATABASE_SERVICE_URL", "SUPABASE_SERVICE_ROLE_KEY"]);
  assert.equal(needles.find((needle) => needle.label === "DATABASE_SERVICE_URL").value, `postgresql://cuadre_jobs:${SECRET}@127.0.0.1:54322/postgres`);
});

test("también se leen los secretos del entorno del proceso (CI)", () => {
  const needles = collectNeedles("", { SUPABASE_SERVICE_ROLE_KEY: SECRET, PATH: "/usr/bin" });
  assert.deepEqual(needles, [{ label: "SUPABASE_SERVICE_ROLE_KEY", value: SECRET }]);
});
