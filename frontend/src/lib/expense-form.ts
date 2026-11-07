// Formulario «Gasto sin factura» ↔ cuerpo de la API (SPEC-W-003 §5.5, AC-11). Puro: lo ejecutan directamente los tests.
//
// El formulario trabaja con TEXTO; la API recibe céntimos enteros. Aquí se cruzan y aquí se cumple «lo que no se puede interpretar se
// señala junto a su campo y no se envía». La API vuelve a validar la forma y decide la fecha (el «hoy» de Madrid).
import type { components } from "@/api/schema";

import { DEFAULT_MANUAL_CATEGORY, isExpenseCategory } from "./expenses.ts";
import { parseAmount } from "./money.ts";
import type { Problem } from "./problems.ts";
import { AMOUNT_ERROR } from "./review.ts";

export type ExpenseBody = components["schemas"]["CreateExpense"];

/** Valores planos del formulario (viajan de ida y vuelta por el estado de una Server Action; nada sensible). */
export type ExpenseFormValues = Record<string, string>;
export type ExpenseErrors = Record<string, string>;
export type ExpenseResult = { ok: true; body: ExpenseBody } | { ok: false; errors: ExpenseErrors };

export const CONCEPT_MAX = 200;
export const EXPENSE_FIELDS = ["expense_date", "concept", "category", "amount"] as const;

// Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API.
const CONTROL = /[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060\ufeff]/g;
const clean = (value: string | undefined) => (value ?? "").replace(CONTROL, " ").replace(/\s+/g, " ").trim();

export const DATE_ERROR = "La fecha no es válida.";
export const DATE_RANGE_ERROR = "La fecha no puede ser futura ni anterior al 1 de enero de 2000.";
export const CONCEPT_ERROR = "Describe el gasto, por ejemplo «Cuota de autónomos».";
export const CATEGORY_ERROR = "Elige una categoría de la lista.";
export const AMOUNT_ZERO_ERROR = "El importe debe ser mayor que cero.";

/** Lee del `FormData` solo los campos conocidos (entrada no confiable: se ignora todo lo demás). */
export function valuesFromExpenseForm(get: (name: string) => unknown): ExpenseFormValues {
  const values: ExpenseFormValues = {};
  for (const name of EXPENSE_FIELDS) {
    const value = get(name);
    values[name] = typeof value === "string" ? value : "";
  }
  return values;
}

function realDay(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

export function toExpenseBody(values: ExpenseFormValues): ExpenseResult {
  const errors: ExpenseErrors = {};

  const concept = clean(values["concept"]);
  if (concept === "") errors["concept"] = CONCEPT_ERROR;
  else if ([...concept].length > CONCEPT_MAX) errors["concept"] = `Máximo ${CONCEPT_MAX} caracteres.`;

  const date = clean(values["expense_date"]);
  if (date === "") errors["expense_date"] = "Elige la fecha del gasto.";
  else if (!realDay(date)) errors["expense_date"] = DATE_ERROR;

  const category = clean(values["category"]);
  if (!isExpenseCategory(category)) errors["category"] = CATEGORY_ERROR;

  const amount = parseAmount(values["amount"] ?? "");
  let cents = 0;
  if (amount.kind === "empty") errors["amount"] = "Escribe el importe del gasto.";
  else if (amount.kind === "invalid") errors["amount"] = AMOUNT_ERROR;
  else if (amount.cents <= 0) errors["amount"] = AMOUNT_ZERO_ERROR;
  else cents = amount.cents;

  if (Object.keys(errors).length > 0 || !isExpenseCategory(category)) return { ok: false, errors };
  return { ok: true, body: { expense_date: date, concept, category, amount_cents: cents } };
}

/** Valores con los que se pinta el formulario por primera vez. */
export function initialExpenseValues(today: string): ExpenseFormValues {
  return { expense_date: today, concept: "", category: DEFAULT_MANUAL_CATEGORY, amount: "" };
}

// --- De un error de la API a un error por campo -----------------------------------------------------------------------------------

/** El campo de la API (`amount_cents`) y el del formulario (`amount`) no se llaman igual; el resto sí. */
const FORM_FIELD: Record<string, string> = {
  expense_date: "expense_date",
  concept: "concept",
  category: "category",
  amount_cents: "amount",
};

// Pydantic escribe sus mensajes en inglés: la interfaz pone el suyo, en español, junto al campo.
const FALLBACK: Record<string, string> = {
  expense_date: DATE_ERROR,
  concept: CONCEPT_ERROR,
  category: CATEGORY_ERROR,
  amount: AMOUNT_ZERO_ERROR,
};

/**
 * Errores por campo de un problema de la API, o `null` si no es de un campo: `invalid_expense` (la fecha fuera de rango, con el
 * texto español de la API) y `validation_error` (la forma del cuerpo, con un texto propio). Los campos vienen de una lista cerrada.
 */
export function fieldErrorsFromProblem(problem: Pick<Problem, "code" | "message" | "field" | "invalidFields">): ExpenseErrors | null {
  if (problem.code === "invalid_expense" && problem.field !== undefined) {
    const name = FORM_FIELD[problem.field];
    return name === undefined ? null : { [name]: problem.message };
  }
  if (problem.code === "validation_error" && problem.invalidFields && problem.invalidFields.length > 0) {
    const errors: ExpenseErrors = {};
    for (const field of problem.invalidFields) {
      const name = FORM_FIELD[field];
      if (name !== undefined) errors[name] = FALLBACK[name] ?? "Revisa este dato.";
    }
    return Object.keys(errors).length > 0 ? errors : null;
  }
  return null;
}
