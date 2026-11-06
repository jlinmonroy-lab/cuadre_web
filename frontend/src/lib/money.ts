// Importes en la interfaz (ADR-0006, RES-02): céntimos ENTEROS en cuanto la persona teclea algo, y `Intl` solo para mostrar.
// Sin dependencias ni alias: lo ejecutan directamente los tests.
//
// `parseAmount` lee lo que se escribe en un campo de importe con la costumbre española: `1.234,50`, `1234,5`, `1234.50`, `12 €`.
// Lo que no se puede leer con seguridad se RECHAZA en vez de adivinarlo: un importe equivocado por 100 es peor que un aviso.
// En particular, `1.200` sin coma es ambiguo (¿mil doscientos o uno con doscientos milésimas?) y no se acepta.

export type Amount = { kind: "empty" } | { kind: "ok"; cents: number } | { kind: "invalid" };

const EMPTY: Amount = Object.freeze({ kind: "empty" });
const INVALID: Amount = Object.freeze({ kind: "invalid" });

/** 12 cifras enteras + 2 decimales: lo que admiten el contrato con los agentes, la API y la base de datos. */
const MAX_INTEGER_DIGITS = 12;

const PLAIN_INTEGER = /^\d+$/;
const GROUPED_INTEGER = /^\d{1,3}(\.\d{3})+$/; // 1.234 · 12.345.678
const DOT_DECIMAL = /^(\d+)\.(\d{1,2})$/; // 1234.5 · 1234.50
const COMMA_FRACTION = /^\d{1,2}$/;

export function parseAmount(input: unknown): Amount {
  if (input === null || input === undefined) return EMPTY;
  if (typeof input !== "string") return INVALID;

  // Espacios (también los de no separación y los estrechos que pone Intl) y el signo del euro no significan nada.
  let text = input.replace(/[\s\u00a0\u202f€]/g, "");
  if (text === "") return EMPTY;

  let negative = false;
  if (text[0] === "-" || text[0] === "\u2212") {
    negative = true;
    text = text.slice(1);
  }

  let integerDigits: string;
  let fraction = "";

  if (text.includes(",")) {
    const parts = text.split(",");
    if (parts.length !== 2) return INVALID; // «1,2,3», «12,50,»
    const [whole = "", decimals = ""] = parts;
    if (!COMMA_FRACTION.test(decimals)) return INVALID; // «12,» · «12,345»
    if (PLAIN_INTEGER.test(whole)) integerDigits = whole;
    else if (GROUPED_INTEGER.test(whole)) integerDigits = whole.replaceAll(".", "");
    else return INVALID; // «,50» · «12.50,00» · «1.2,50»
    fraction = decimals;
  } else if (PLAIN_INTEGER.test(text)) {
    integerDigits = text;
  } else {
    const decimal = DOT_DECIMAL.exec(text);
    if (!decimal) return INVALID; // «1.200» (ambiguo), «1e3», «NaN», «1.2.3»
    integerDigits = decimal[1] ?? "";
    fraction = decimal[2] ?? "";
  }

  if (integerDigits.length > MAX_INTEGER_DIGITS) return INVALID;

  // Aritmética entera: como mucho 12 cifras enteras, así que `Number` es exacto y el resultado cabe de sobra en 2^53.
  const magnitude = Number(integerDigits) * 100 + Number(fraction.padEnd(2, "0"));
  return { kind: "ok", cents: negative && magnitude !== 0 ? -magnitude : magnitude };
}

/** Céntimos de lo escrito, o `null` si está vacío o no se puede interpretar (para distinguirlos, usa `parseAmount`). */
export function parseCents(input: unknown): number | null {
  const amount = parseAmount(input);
  return amount.kind === "ok" ? amount.cents : null;
}

/** Valor para un campo de importe: `1234,50` (coma decimal, dos decimales, sin agrupar). Vacío si no hay importe. */
export function centsToInput(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || !Number.isSafeInteger(cents)) return "";
  const magnitude = Math.abs(cents);
  const remainder = magnitude % 100;
  const euros = (magnitude - remainder) / 100; // división exacta: `remainder` es lo que sobra
  return `${cents < 0 ? "-" : ""}${euros},${String(remainder).padStart(2, "0")}`;
}

const EURO = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });

/** Importe para mostrar (`1.234,50 €`). «—» si no hay importe. */
export function formatCents(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || !Number.isSafeInteger(cents)) return "—";
  return EURO.format(cents / 100);
}
