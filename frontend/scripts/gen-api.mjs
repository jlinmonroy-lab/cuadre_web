// Genera src/api/schema.d.ts a partir de backend/openapi.json (que a su vez sale de las rutas de FastAPI).
//   node scripts/gen-api.mjs           regenera el archivo
//   node scripts/gen-api.mjs --check   falla (código 1) si el archivo versionado no coincide; no escribe nada
// El archivo generado no se edita a mano (CLAUDE.md, prohibición 9).
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const SOURCE = new URL("../../backend/openapi.json", import.meta.url);
const TARGET = new URL("../src/api/schema.d.ts", import.meta.url);
const HEADER = [
  "/**",
  " * GENERADO por `npm run gen:api` a partir de backend/openapi.json. NO se edita a mano.",
  " * Para cambiarlo: modifica las rutas de la API, ejecuta `python backend/scripts/export_openapi.py` y `npm --prefix frontend run gen:api`.",
  " */",
  "",
  "",
].join("\n");

const check = process.argv.includes("--check");

if (!existsSync(SOURCE)) {
  console.error(`No existe ${fileURLToPath(SOURCE)}. Ejecuta antes: python backend/scripts/export_openapi.py`);
  process.exit(1);
}

const generated = HEADER + astToString(await openapiTS(SOURCE, { alphabetize: true }));
const normalize = (text) => text.replaceAll("\r\n", "\n");

if (check) {
  const current = existsSync(TARGET) ? normalize(readFileSync(TARGET, "utf8")) : null;
  if (current !== generated) {
    console.error("frontend/src/api/schema.d.ts no coincide con backend/openapi.json. Ejecuta: npm --prefix frontend run gen:api");
    process.exit(1);
  }
  console.log("frontend/src/api/schema.d.ts está al día.");
} else {
  writeFileSync(TARGET, generated, "utf8");
  console.log(`Escrito ${fileURLToPath(TARGET)}`);
}
