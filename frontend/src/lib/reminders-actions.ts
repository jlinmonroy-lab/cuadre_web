"use server";

// Server Action de los recordatorios: guardar si se quieren y con cuántos días de antelación. Es CORTA (no espera a ningún servicio externo). Lo
// que recibe es entrada no confiable (las Server Actions son POST públicos y el proxy no las ve): se valida la forma aquí, se comprueba la sesión y
// la API vuelve a decidir (403 al gestor y al administrador, 422 con su texto). No hay ninguna regla aquí: el rango lo decide el servidor.
import { refresh } from "next/cache";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import type { FormState } from "@/lib/form-state";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";
import { fieldErrorsFromRemindersProblem, toRemindersBody, valuesFromRemindersForm } from "@/lib/reminders-form";

const SAVED = "Recordatorios guardados.";

function asValues(values: { enabled: boolean; lead_days: string }): Record<string, string> {
  return { enabled: values.enabled ? "on" : "", lead_days: values.lead_days };
}

export async function saveReminders(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromRemindersForm((name) => formData.get(name));
  const parsed = toRemindersBody(values);
  if (!parsed.ok) return { status: "error", fieldErrors: parsed.errors, values: asValues(values) };

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/me/reminders", { body: parsed.body });
  } catch {
    return { status: "error", message: SERVICE_UNAVAILABLE.message, values: asValues(values) };
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: SAVED, values: asValues({ enabled: result.data.enabled, lead_days: String(result.data.lead_days) }) };
  }
  const problem = problemOf(result.response, result.error);
  const fieldErrors = fieldErrorsFromRemindersProblem(problem);
  return fieldErrors
    ? { status: "error", message: problem.message, fieldErrors, values: asValues(values) }
    : { status: "error", message: problem.message, values: asValues(values) };
}
