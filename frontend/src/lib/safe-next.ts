// `?next=` y el parámetro `next` de /auth/confirm acaban en una redirección: solo se admiten rutas de esta misma aplicación.
// Sin dependencias ni alias: lo ejecutan directamente los tests (`node --test`).

const MAX_LENGTH = 512;
// Controles C0 y C1, DEL y los separadores de línea de Unicode: los navegadores ignoran tabuladores y saltos dentro de una URL,
// así que «/\t/evil.com» acabaría siendo «//evil.com».
const CONTROL = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/;

function isLocalPath(value: string, { allowSpaces }: { allowSpaces: boolean }): boolean {
  if (value[0] !== "/") return false;
  if (value[1] === "/") return false; // «//host» es una dirección con host (y «/\host», que los navegadores leen igual, lleva barra invertida)
  if (value.includes("\\") || CONTROL.test(value)) return false;
  if (!allowSpaces && /\s/.test(value)) return false;
  return true;
}

/** Devuelve `raw` si es una ruta relativa segura; si no, `fallback` (que debe ser una constante del código, no una entrada). */
export function safeNext(raw: unknown, fallback = "/"): string {
  if (typeof raw !== "string" || raw.length === 0 || raw.length > MAX_LENGTH) return fallback;
  if (!isLocalPath(raw, { allowSpaces: false })) return fallback;

  // Se comprueba también la forma decodificada: «/%2f%2fevil.com» y «/%5cevil.com» no deben pasar por si algo la decodifica después.
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return fallback;
  }
  if (!isLocalPath(decoded, { allowSpaces: true })) return fallback;

  return new URL(raw, "http://localhost").origin === "http://localhost" ? raw : fallback;
}
