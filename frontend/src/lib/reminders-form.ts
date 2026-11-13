// Formulario de recordatorios ↔ cuerpo de la API (SPEC-W-014 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz NO decide el rango de la antelación (1 a 30): lo decide el servidor, con su texto. Aquí solo se cruza texto con el cuerpo (la
// antelación es lo único que cambia de tipo) y se señala lo que no se puede ni enviar (algo que no es un número entero).
import type { components } from "@/api/schema";

import type { Problem } from "./problems.ts";

export type RemindersBody = components["schemas"]["ReminderSettingsInput"];
export type RemindersValues = { enabled: boolean; lead_days: string };
export type RemindersErrors = Record<string, string>;
export type RemindersResult = { ok: true; body: RemindersBody } | { ok: false; errors: RemindersErrors };

export const LEAD_DAYS_ERROR = "La antelación debe ser un número entero de días entre 1 y 30.";

/** Valores con los que se pinta el formulario: lo guardado. */
export function valuesFromSettings(settings: { enabled: boolean; lead_days: number }): RemindersValues {
  return { enabled: settings.enabled, lead_days: String(settings.lead_days) };
}

/** Lee del `FormData` solo los campos conocidos (entrada no confiable). Una casilla sin marcar no viaja en el formulario: ausente es `false`. */
export function valuesFromRemindersForm(get: (name: string) => unknown): RemindersValues {
  const days = get("lead_days");
  return { enabled: get("enabled") === "on", lead_days: typeof days === "string" ? days : "" };
}

export function toRemindersBody(values: RemindersValues): RemindersResult {
  const raw = values.lead_days.trim();
  if (!/^-?\d{1,6}$/.test(raw)) return { ok: false, errors: { lead_days: LEAD_DAYS_ERROR } };
  return { ok: true, body: { enabled: values.enabled, lead_days: Number(raw) } };
}

/** De un `invalid_lead_days` a un error junto al campo (el texto es del servidor). `null` si el problema no es de ese campo. */
export function fieldErrorsFromRemindersProblem(problem: Problem): RemindersErrors | null {
  if (problem.code !== "invalid_lead_days") return null;
  return { lead_days: problem.message };
}
