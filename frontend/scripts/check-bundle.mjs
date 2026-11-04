// `npm run check:bundle`: tras `next build`, comprueba que nada de .next contiene la clave de servicio ni URL de base de datos
// (SPEC-W-001 AC-15, T-15). Las comprobaciones sobre el código fuente están en backend/tests/rules/test_frontend_scope.py.
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { STATIC_NEEDLES, collectNeedles, findLeaks } from "./bundle-scan.mjs";

const BUILD = new URL("../.next/", import.meta.url);
const ROOT_ENV = new URL("../../.env", import.meta.url);

if (!existsSync(BUILD)) {
  console.error("No hay .next: ejecuta antes `npm --prefix frontend run build`.");
  process.exit(1);
}

const envText = existsSync(ROOT_ENV) ? readFileSync(ROOT_ENV, "utf8") : "";
const needles = [
  ...STATIC_NEEDLES,
  ...collectNeedles(envText, process.env).map(({ label, value }) => ({ label: `el valor de ${label}`, value })),
];

const hits = findLeaks(fileURLToPath(BUILD), needles);
if (hits.length > 0) {
  for (const { file, label } of hits) console.error(`FUGA: ${file} contiene ${label}`);
  process.exit(1);
}
console.log(`check:bundle OK (${needles.length} cadenas buscadas; ninguna en .next).`);
