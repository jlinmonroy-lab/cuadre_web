// Qué hacer cuando GET /api/me no devuelve 200. Sin dependencias ni alias: lo ejecutan directamente los tests.
//
// Solo un 401 o un 403 con motivo de cuenta cierran la sesión. Un fallo de la API (red, 5xx, 429…) nunca la cierra ni redirige a
// /login: eso provocaría un bucle login ↔ raíz y perdería sesiones válidas durante una caída.

export type MeFailure = { status?: number; code?: string };
export type MeFailureAction = "sign-out" | "suspended" | "profile-missing" | "unavailable";

export function classifyMeFailure({ status, code }: MeFailure): MeFailureAction {
  if (status === 401) return "sign-out";
  if (status === 403 && code === "account_suspended") return "suspended";
  if (status === 403 && code === "profile_missing") return "profile-missing";
  return "unavailable";
}
