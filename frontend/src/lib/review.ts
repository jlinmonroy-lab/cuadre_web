// Formulario de revisión ↔ cuerpo de la API (SPEC-W-002 §5.1, §5.3, AC-14). Puro: lo ejecutan directamente los tests.
//
// El formulario trabaja con TEXTO (lo que la persona ve y teclea); la API recibe céntimos enteros. Este módulo es el único sitio
// donde se cruzan, y es donde se cumple «un importe que no se puede interpretar se señala junto al campo y no se guarda»:
// `toReviewBody` devuelve un error POR CAMPO y ningún cuerpo si algo no se entiende. La API vuelve a validar la forma.
import type { components } from "@/api/schema";

import { DOC_TYPES } from "./documents.ts";
import { centsToInput, parseAmount } from "./money.ts";

export type ReviewBody = components["schemas"]["Review"];
type Extraction = components["schemas"]["Extraction"];

/** Valores del formulario, planos (viajan de ida y vuelta por el estado de una Server Action). Nunca llevan nada sensible. */
export type FormValues = Record<string, string>;
export type ReviewErrors = Record<string, string>;
export type ReviewResult = { ok: true; body: ReviewBody } | { ok: false; errors: ReviewErrors };

export const MAX_LINES = 10;
export const TEXT_LIMITS = { supplier_name: 200, supplier_tax_id: 32, recipient_tax_id: 32, invoice_number: 64 } as const;

export const AMOUNT_ERROR = "No entendemos este importe. Escríbelo así: 1.234,50";
const RATE_ERROR = "El tipo no es válido. Escribe un número, por ejemplo 21 o 7,5.";

export const lineName = (index: number, part: "rate" | "base" | "vat") => `line_${index}_${part}`;

const TEXT_FIELDS = Object.keys(TEXT_LIMITS) as (keyof typeof TEXT_LIMITS)[];

// --- De la API al formulario ------------------------------------------------------------------------------------------------------

const rateToInput = (rate: string | null | undefined) => (rate ? rate.replace(".", ",") : "");

/** Valores iniciales: lo corregido si existe y, si no, lo leído. Un documento que no se pudo leer parte de un formulario vacío. */
export function initialValues(source: { extraction: Extraction | null; review: ReviewBody | null }): FormValues {
  const shown: ReviewBody | Extraction | null = source.review ?? source.extraction;
  const lines = shown?.tax_breakdown ?? [];
  const values: FormValues = {
    doc_type: shown?.doc_type ?? "",
    supplier_name: shown?.supplier_name ?? "",
    supplier_tax_id: shown?.supplier_tax_id ?? "",
    recipient_tax_id: shown?.recipient_tax_id ?? "",
    invoice_number: shown?.invoice_number ?? "",
    issue_date: shown?.issue_date ?? "",
    currency: shown?.currency ?? "",
    total: centsToInput(shown?.total_cents),
    withholding_rate: rateToInput(shown?.withholding?.rate),
    withholding_amount: centsToInput(shown?.withholding?.amount_cents),
    line_count: String(Math.min(Math.max(lines.length, 1), MAX_LINES)),
  };
  for (const [index, line] of lines.slice(0, MAX_LINES).entries()) {
    values[lineName(index, "rate")] = rateToInput(line.vat_rate);
    values[lineName(index, "base")] = centsToInput(line.base_cents);
    values[lineName(index, "vat")] = centsToInput(line.vat_cents);
  }
  return values;
}

export function lineCount(values: FormValues): number {
  const count = Number.parseInt(values["line_count"] ?? "", 10);
  return Number.isInteger(count) ? Math.min(Math.max(count, 1), MAX_LINES) : 1;
}

/** Lee del `FormData` solo los campos conocidos (entrada no confiable: se ignora todo lo demás). */
export function valuesFromForm(get: (name: string) => unknown): FormValues {
  const read = (name: string) => {
    const value = get(name);
    return typeof value === "string" ? value : "";
  };
  const values: FormValues = {};
  for (const name of ["doc_type", "supplier_name", "supplier_tax_id", "recipient_tax_id", "invoice_number", "issue_date", "currency", "total", "withholding_rate", "withholding_amount", "line_count"]) {
    values[name] = read(name);
  }
  const count = lineCount(values);
  values["line_count"] = String(count);
  for (let index = 0; index < count; index++) {
    for (const part of ["rate", "base", "vat"] as const) values[lineName(index, part)] = read(lineName(index, part));
  }
  return values;
}

// --- Del formulario a la API ------------------------------------------------------------------------------------------------------

// Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API.
const CONTROL = /[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060\ufeff]/g;
const clean = (value: string | undefined) => (value ?? "").replace(CONTROL, " ").replace(/\s+/g, " ").trim();
const length = (value: string) => [...value].length;

function parseDate(value: string): string | null | "invalid" {
  if (value === "") return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return "invalid";
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  const real = date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  return real ? value : "invalid";
}

function parseRate(value: string): string | null | "invalid" {
  const text = value.replace(/\s/g, "").replace(",", ".");
  if (text === "") return null;
  return /^\d{1,3}(\.\d{1,2})?$/.test(text) ? text : "invalid";
}

export function toReviewBody(values: FormValues): ReviewResult {
  const errors: ReviewErrors = {};
  const amount = (name: string, raw: string | undefined): number | null => {
    const parsed = parseAmount(raw ?? "");
    if (parsed.kind === "invalid") {
      errors[name] = AMOUNT_ERROR;
      return null;
    }
    return parsed.kind === "ok" ? parsed.cents : null;
  };
  const rate = (name: string, raw: string | undefined): string | null => {
    const parsed = parseRate(raw ?? "");
    if (parsed === "invalid") {
      errors[name] = RATE_ERROR;
      return null;
    }
    return parsed;
  };

  const text: Record<string, string | null> = {};
  for (const field of TEXT_FIELDS) {
    const value = clean(values[field]);
    if (length(value) > TEXT_LIMITS[field]) errors[field] = `Máximo ${TEXT_LIMITS[field]} caracteres.`;
    text[field] = value === "" ? null : value;
  }

  const docType = clean(values["doc_type"]);
  if (docType !== "" && !(DOC_TYPES as readonly string[]).includes(docType)) errors["doc_type"] = "Elige un tipo de documento de la lista.";

  const date = parseDate(clean(values["issue_date"]));
  if (date === "invalid") errors["issue_date"] = "La fecha no es válida.";

  const currency = clean(values["currency"]).toUpperCase();
  if (currency !== "" && !/^[A-Z]{3}$/.test(currency)) errors["currency"] = "Escribe el código de 3 letras, por ejemplo EUR.";

  const total = amount("total", values["total"]);

  const requested = Number.parseInt(values["line_count"] ?? "", 10);
  if (Number.isInteger(requested) && requested > MAX_LINES) errors["line_count"] = `Como máximo ${MAX_LINES} líneas de IVA.`;
  const taxBreakdown: NonNullable<ReviewBody["tax_breakdown"]> = [];
  for (let index = 0; index < lineCount(values); index++) {
    const fields = [values[lineName(index, "rate")], values[lineName(index, "base")], values[lineName(index, "vat")]];
    if (fields.every((field) => clean(field) === "")) continue; // una línea en blanco no se envía
    taxBreakdown.push({
      vat_rate: rate(lineName(index, "rate"), fields[0]),
      base_cents: amount(lineName(index, "base"), fields[1]),
      vat_cents: amount(lineName(index, "vat"), fields[2]),
    });
  }

  const withholdingRate = rate("withholding_rate", values["withholding_rate"]);
  const withholdingAmount = amount("withholding_amount", values["withholding_amount"]);
  const withholding = withholdingRate === null && withholdingAmount === null ? null : { rate: withholdingRate, amount_cents: withholdingAmount };

  if (Object.keys(errors).length > 0) return { ok: false, errors };
  return {
    ok: true,
    body: {
      doc_type: docType === "" ? null : (docType as NonNullable<ReviewBody["doc_type"]>),
      supplier_name: text["supplier_name"] ?? null,
      supplier_tax_id: text["supplier_tax_id"] ?? null,
      recipient_tax_id: text["recipient_tax_id"] ?? null,
      invoice_number: text["invoice_number"] ?? null,
      issue_date: date === "invalid" ? null : date,
      currency: currency === "" ? null : currency,
      tax_breakdown: taxBreakdown,
      withholding,
      total_cents: total,
    },
  };
}
