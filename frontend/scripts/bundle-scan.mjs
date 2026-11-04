// Lógica de `check-bundle.mjs`: busca en lo que se construye (y se serviría al navegador o correría en Next) cualquier rastro de
// la clave de servicio o de las URL de base de datos. SPEC-W-001 AC-15 y T-15.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

/** Rastros que no deben aparecer nunca en el resultado del build. El prefijo suelto «sb_secret_» NO cuenta: supabase-js lo usa en una
 *  comprobación de prefijo (`startsWith`); lo que no puede haber es una clave entera. */
export const STATIC_NEEDLES = [
  { label: "la cadena «SERVICE_ROLE»", value: "SERVICE_ROLE" },
  { label: "una clave secreta de Supabase (sb_secret_…)", pattern: /sb_secret_[A-Za-z0-9_-]{20,}/ },
];

/** Variables del .env raíz (o del entorno en CI) cuyo VALOR no puede aparecer en el build. */
const SECRET_VARIABLES = [
  "SUPABASE_SERVICE_ROLE_KEY",
  "DATABASE_URL",
  "DATABASE_SERVICE_URL",
  "TEST_DATABASE_ADMIN_URL",
  "ADMIN_PASSWORD",
  "MCP_TOKEN_SECRET",
  "INTERNAL_JOBS_SECRET",
  "AGENTS_API_KEY",
];

const MIN_SECRET_LENGTH = 8; // por debajo, una coincidencia sería casual
const SKIPPED_TOP_LEVEL = new Set(["cache", "dev"]); // caché de compilación y artefactos del servidor de desarrollo
const MAX_FILE_BYTES = 25 * 1024 * 1024;

const isRealSecret = (value) => value.length >= MIN_SECRET_LENGTH && !(value.startsWith("<") && value.endsWith(">"));

/** Valores a buscar: los de `envText` (contenido de un .env) y los del entorno del proceso. */
export function collectNeedles(envText, processEnv) {
  const values = new Map();
  for (const line of envText.split(/\r?\n/)) {
    const match = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
    if (!match || !SECRET_VARIABLES.includes(match[1])) continue;
    values.set(match[1], match[2].split(/\s+#/)[0].trim());
  }
  for (const name of SECRET_VARIABLES) if (processEnv[name]) values.set(name, processEnv[name]);
  return [...values].filter(([, value]) => isRealSecret(value)).map(([label, value]) => ({ label, value }));
}

function* files(dir, topLevel = true) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      // Solo se omiten en la raíz de .next: una ruta de la aplicación llamada «cache» o «dev» sí se revisa.
      if (!(topLevel && SKIPPED_TOP_LEVEL.has(entry.name))) yield* files(path, false);
    } else if (entry.isFile() && statSync(path).size <= MAX_FILE_BYTES) {
      yield path;
    }
  }
}

/** Cada aguja es `{ label, value }` (cadena literal) o `{ label, pattern }` (RegExp).
 *  Devuelve `{ file, label }` por cada fichero que contiene alguna de ellas (ruta relativa a `dir`, con `/`). */
export function findLeaks(dir, needles) {
  const hits = [];
  for (const path of files(dir)) {
    const text = readFileSync(path).toString("latin1"); // sin decodificar UTF-8: basta para cadenas ASCII, incluso en binarios
    for (const { label, value, pattern } of needles) {
      if (pattern ? pattern.test(text) : text.includes(value)) hits.push({ file: relative(dir, path).split(sep).join("/"), label });
    }
  }
  return hits;
}
