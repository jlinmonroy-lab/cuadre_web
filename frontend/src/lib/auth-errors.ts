// De los errores de Supabase Auth a mensajes en español que no revelan si una cuenta existe (SPEC-W-001 §5.3).
// Sin dependencias ni alias: lo ejecutan directamente los tests.

export type AuthFailure = { code?: string; status?: number; message?: string } | null | undefined;

const RATE_MESSAGE = "Demasiados intentos. Espera unos minutos.";
const RATE_CODES = new Set(["over_request_rate_limit", "over_email_send_rate_limit"]);
// Cuenta inexistente, contraseña errónea y correo sin confirmar se muestran igual a propósito.
const WRONG_CREDENTIALS_CODES = new Set([
  "invalid_credentials",
  "email_not_confirmed",
  "user_not_found",
  "invalid_grant",
  "user_banned",
]);
const ALREADY_REGISTERED_CODES = new Set(["user_already_exists", "email_exists"]);

const isRateLimited = (error: NonNullable<AuthFailure>) =>
  error.status === 429 || (error.code !== undefined && RATE_CODES.has(error.code));

export function loginMessage(error: AuthFailure): string {
  if (error && isRateLimited(error)) return RATE_MESSAGE;
  if (error && ((error.code !== undefined && WRONG_CREDENTIALS_CODES.has(error.code)) || error.message === "Invalid login credentials")) {
    return "Correo o contraseña incorrectos.";
  }
  return "No hemos podido iniciar sesión. Inténtalo de nuevo.";
}

export type SignupOutcome =
  | { kind: "sent" }
  | { kind: "field"; field: "password"; message: string }
  | { kind: "error"; message: string };

export function signupOutcome(error: AuthFailure): SignupOutcome {
  if (!error) return { kind: "sent" };
  // «Ya existe» responde igual que el éxito: de lo contrario el formulario serviría para descubrir qué correos están registrados.
  if (error.code !== undefined && ALREADY_REGISTERED_CODES.has(error.code)) return { kind: "sent" };
  if (error.code === "weak_password") {
    return { kind: "field", field: "password", message: "La contraseña es demasiado débil. Prueba con una más larga o menos habitual." };
  }
  if (isRateLimited(error)) return { kind: "error", message: RATE_MESSAGE };
  if (error.code === "signup_disabled") return { kind: "error", message: "El registro no está disponible ahora mismo." };
  return { kind: "error", message: "No hemos podido crear la cuenta. Inténtalo de nuevo." };
}

export type RecoveryOutcome = { kind: "sent" } | { kind: "error"; message: string };

export function recoveryOutcome(error: AuthFailure): RecoveryOutcome {
  // Solo el límite de envíos se distingue: no depende de que la cuenta exista. Cualquier otro fallo responde como el éxito.
  if (error && isRateLimited(error)) return { kind: "error", message: RATE_MESSAGE };
  return { kind: "sent" };
}

export type ResetOutcome =
  | { kind: "done" }
  | { kind: "expired" }
  | { kind: "field"; field: "password"; message: string }
  | { kind: "error"; message: string };

const EXPIRED_CODES = new Set(["session_not_found", "session_expired", "refresh_token_not_found"]);

export function resetOutcome(error: AuthFailure): ResetOutcome {
  if (!error) return { kind: "done" };
  if (error.code === "same_password") {
    return { kind: "field", field: "password", message: "Elige una contraseña distinta de la anterior." };
  }
  if (error.code === "weak_password") {
    return { kind: "field", field: "password", message: "La contraseña es demasiado débil. Prueba con una más larga o menos habitual." };
  }
  if (isRateLimited(error)) return { kind: "error", message: RATE_MESSAGE };
  // El enlace de recuperación crea una sesión de vida corta: si ya no existe, hay que pedir otro enlace.
  if (error.status === 401 || (error.code !== undefined && EXPIRED_CODES.has(error.code))) return { kind: "expired" };
  return { kind: "error", message: "No hemos podido cambiar la contraseña. Inténtalo de nuevo." };
}
