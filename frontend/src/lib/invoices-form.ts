// Formularios de factura y de rectificativa ↔ cuerpo de la API (SPEC-W-007 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y no valida nada fiscal: ni el cliente, ni la serie, ni la fecha, ni el IVA. Aquí solo se cruza
// texto con el cuerpo (vacío = `null`) y el importe tecleado en euros se pasa a céntimos ENTEROS con `parseAmount` (un `1.200` ambiguo o un
// texto ilegible se envía como `null` y el servidor dice qué importe espera). Los textos de los errores son del servidor.
import type { components } from "@/api/schema";

import { parseAmount } from "./money.ts";
import type { FormState } from "./form-state.ts";
import type { Problem } from "./problems.ts";

export type InvoiceBody = components["schemas"]["InvoiceInput"];
export type RectificationBody = components["schemas"]["RectificationInput"];
export type InvoiceValues = Record<string, string>;
export type InvoiceErrors = Record<string, string>;

/** Estado de un formulario de facturas: además del de siempre, el código del error (para enlaces) y lo que falta en el perfil. */
export type InvoiceFormState = FormState & { code?: string; missing?: { field: string; label: string }[] };

/** Los campos de «Nueva factura», en el orden de la pantalla. `base` es el importe en euros que teclea la persona. */
export const INVOICE_FORM_FIELDS = ["client_id", "series_id", "issue_date", "concept", "base", "vat_rate"] as const;
/** Los campos de «Emitir rectificativa». `annul` es la casilla «Anular por completo». */
export const RECTIFY_FORM_FIELDS = ["reason", "corrected_base", "annul", "issue_date"] as const;

/** Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API. */
const code = (n: number) => String.fromCharCode(n);
const CONTROL = new RegExp(
  `[${code(0)}-${code(0x1f)}${code(0x7f)}-${code(0x9f)}${code(0x200b)}-${code(0x200f)}${code(0x2028)}-${code(0x202e)}${code(0x2060)}${code(0xfeff)}]`,
  "g",
);

const orNull = (value: string | undefined): string | null => {
  const text = (value ?? "").replace(CONTROL, " ").trim();
  return text === "" ? null : text;
};

/** Céntimos de lo tecleado, o `null` si está vacío o no se puede leer con seguridad (que el servidor lo explique). */
const centsOrNull = (text: string | undefined): number | null => {
  const amount = parseAmount(text);
  return amount.kind === "ok" ? amount.cents : null;
};

function read(names: readonly string[], get: (name: string) => unknown): InvoiceValues {
  const values: InvoiceValues = {};
  for (const name of names) {
    const value = get(name);
    values[name] = typeof value === "string" ? value : "";
  }
  return values;
}

/** Lee del `FormData` solo los campos conocidos (entrada no confiable: se ignora todo lo demás, también un `kind` o un `total_cents`). */
export const valuesFromInvoiceForm = (get: (name: string) => unknown): InvoiceValues => read(INVOICE_FORM_FIELDS, get);
export const valuesFromRectifyForm = (get: (name: string) => unknown): InvoiceValues => read(RECTIFY_FORM_FIELDS, get);

/** El cuerpo de la API para emitir o previsualizar. Sin tipo de IVA = el del tratamiento; sin serie = la predeterminada. */
export function toInvoiceBody(values: InvoiceValues): InvoiceBody {
  return {
    client_id: orNull(values["client_id"]),
    series_id: orNull(values["series_id"]),
    issue_date: orNull(values["issue_date"]),
    concept: orNull(values["concept"]),
    base_cents: centsOrNull(values["base"]),
    vat_rate: orNull(values["vat_rate"]),
  };
}

/** El importe de la vista previa en directo: `empty` (nada escrito), `invalid` (ilegible) u `ok`. */
export type PreviewBase = "ok" | "empty" | "invalid";
const PLACEHOLDER_BASE_CENTS = 100_000;
const PLACEHOLDER_CONCEPT = "Vista previa";

/**
 * La petición de la vista previa. Todavía no hay importe, concepto o fecha válidos mientras se teclea, y el servidor valida todo a la vez: lo que
 * falta se rellena con valores neutros para que conteste con el ámbito, el tipo de IVA y la mención. Si el importe no es válido, `base` lo dice
 * para que la pantalla NO enseñe los importes inventados.
 */
export function toPreviewRequest(values: InvoiceValues, today: string): { body: InvoiceBody; base: PreviewBase } {
  const amount = parseAmount(values["base"]);
  const base: PreviewBase = amount.kind === "ok" && amount.cents > 0 ? "ok" : amount.kind === "empty" ? "empty" : "invalid";
  const body = toInvoiceBody(values);
  return {
    base,
    body: {
      ...body,
      concept: body.concept ?? PLACEHOLDER_CONCEPT,
      issue_date: body.issue_date ?? today,
      base_cents: base === "ok" ? body.base_cents : PLACEHOLDER_BASE_CENTS,
    },
  };
}

/** El cuerpo de la API para rectificar. «Anular por completo» fija la base corregida en 0, escriba lo que escriba la persona en su campo. */
export function toRectificationBody(values: InvoiceValues): RectificationBody {
  const annul = values["annul"] === "on";
  return {
    reason: orNull(values["reason"]),
    corrected_base_cents: annul ? 0 : centsOrNull(values["corrected_base"]),
    issue_date: orNull(values["issue_date"]),
  };
}

// --- Errores del servidor → campos de la pantalla ----------------------------------------------------------------------------------

/** Campo de la API → campo de la pantalla, para cada formulario. Lo que un formulario no tiene se descarta. */
const SCREEN_FIELDS = {
  invoice: { client_id: "client_id", series_id: "series_id", issue_date: "issue_date", concept: "concept", base_cents: "base", vat_rate: "vat_rate" },
  rectification: { reason: "reason", corrected_base_cents: "corrected_base", issue_date: "issue_date" },
} as const satisfies Record<string, Record<string, string>>;

export type FormTarget = keyof typeof SCREEN_FIELDS;

/** `client_id` con el domicilio vacío (`client_not_billable`, `field: "address"`) sigue siendo un problema de la elección de cliente. */
const SINGLE_FIELD_CODES = new Set(["client_not_billable", "series_exhausted", "invoice_date_out_of_order"]);

/**
 * De un `invalid_invoice` a un error por campo (todos a la vez, con el texto del servidor) y de los problemas de UN campo (cliente no
 * facturable, serie agotada, fecha fuera de orden) a un error junto a ese campo. `null` si el problema no es de campos.
 */
export function fieldErrorsFromInvoiceProblem(problem: Problem, target: FormTarget): InvoiceErrors | null {
  const names: Record<string, string> = SCREEN_FIELDS[target];
  const errors: InvoiceErrors = {};
  if (problem.code === "invalid_invoice" && problem.invoiceFields) {
    for (const { field, message } of problem.invoiceFields) {
      const name = names[field];
      if (name) errors[name] ??= message;
    }
  } else if (SINGLE_FIELD_CODES.has(problem.code) && problem.field) {
    const name = names[problem.field === "address" ? "client_id" : problem.field];
    if (name) errors[name] = problem.message;
  }
  return Object.keys(errors).length > 0 ? errors : null;
}

/**
 * El estado que vuelve al formulario tras un error de la API. Con errores de campo, cada texto va junto a su campo y en el resumen; el titular
 * solo se añade si dice algo más que ellos (el de un solo campo ya ES el texto del campo: repetirlo sería leerlo dos veces). `profile_incomplete`
 * lleva la lista de lo que falta, por nombre, para enlazar con el perfil.
 */
export function invoiceFailure(problem: Problem, values: InvoiceValues, target: FormTarget): InvoiceFormState {
  const base = { status: "error", values, code: problem.code } as const;
  if (problem.code === "profile_incomplete" && problem.missing) return { ...base, message: problem.message, missing: problem.missing };
  const fieldErrors = fieldErrorsFromInvoiceProblem(problem, target);
  if (!fieldErrors) return { ...base, message: problem.message };
  return SINGLE_FIELD_CODES.has(problem.code) ? { ...base, fieldErrors } : { ...base, message: problem.message, fieldErrors };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
/** Los ids de factura son UUID: lo demás ni se envía a la API. */
export const isInvoiceId = (value: unknown): value is string => typeof value === "string" && UUID.test(value);
