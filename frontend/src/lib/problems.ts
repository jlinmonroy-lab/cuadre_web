// Errores de la API (`application/problem+json`, SPEC-W-001 §5.1) → lo que ve la persona. Puro: lo ejecutan directamente los tests.
//
// Los `detail` de la API ya vienen en español y sin datos, pero llegan por la red: solo se enseñan si son texto corto de un error
// 4xx. Un 5xx nunca enseña su cuerpo (podría llevar rutas o trazas de un servicio intermedio).

import { isCheckCode } from "./expenses.ts";

export type Problem = {
  status: number;
  code: string;
  message: string;
  retryAfter?: number;
  /** `invalid_expense`: el campo de la API que falla (`expense_date`, `concept`, `category` o `amount_cents`). */
  field?: string;
  /** `validation_failed`: las comprobaciones que no pasan, por su código. */
  failedChecks?: string[];
  /** `validation_error`: los campos de un cuerpo mal formado (los mismos nombres que `field`). */
  invalidFields?: string[];
  /** `invalid_profile`: TODOS los campos del perfil que fallan, cada uno con su texto (el servidor no repite lo escrito). */
  profileFields?: { field: string; message: string }[];
  /** `invalid_client`: TODOS los campos de la ficha de cliente que fallan, cada uno con su texto (el servidor no repite lo escrito). */
  clientFields?: { field: string; message: string }[];
};

const BY_STATUS: Record<number, string> = {
  401: "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.",
  403: "Tu cuenta no tiene permiso para hacer esto.",
  404: "No encontramos ese documento.",
};
const UNAVAILABLE = "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.";
const GENERIC = "No hemos podido completar la operación. Inténtalo de nuevo.";

const CODE = /^[a-z][a-z0-9_]{0,63}$/;
// Los campos y las ubicaciones que se aceptan de un error de la API vienen de listas cerradas: nunca se refleja texto libre del cuerpo.
const FIELDS = new Set(["expense_date", "concept", "category", "amount_cents", "code", "description", "first_number"]);
// SPEC-W-005: los campos del perfil que puede señalar `invalid_profile`.
export const PROFILE_FIELDS = [
  "legal_name",
  "tax_id",
  "fiscal_address",
  "activity",
  "iae_epigraph",
  "activity_start_date",
  "vat_regime",
  "irpf_rate",
  "home_pct",
  "iban",
] as const;
const PROFILE_FIELD_SET: ReadonlySet<string> = new Set(PROFILE_FIELDS);
// SPEC-W-006: los campos de la ficha de cliente que puede señalar `invalid_client`, en el orden de la pantalla.
export const CLIENT_FIELDS = ["name", "kind", "country", "tax_id", "address"] as const;
const CLIENT_FIELD_SET: ReadonlySet<string> = new Set(CLIENT_FIELDS);
const FIELD_LOCS = new Map([
  ["body.expense_date", "expense_date"],
  ["body.concept", "concept"],
  ["body.category", "category"],
  ["body.amount_cents", "amount_cents"],
]);
const UNSAFE_TEXT = /[\u0000-\u001f\u007f-\u009f<>]/;
const MAX_DETAIL = 300;
const MAX_RETRY_AFTER = 300;

export function describeProblem(input: { status: number; body: unknown; retryAfter?: string | null }): Problem {
  const body = typeof input.body === "object" && input.body !== null && !Array.isArray(input.body) ? (input.body as Record<string, unknown>) : {};
  const code = typeof body["code"] === "string" && CODE.test(body["code"]) ? body["code"] : "error";
  const detail = body["detail"];
  const showable = input.status >= 400 && input.status < 500 && typeof detail === "string" && detail.length > 0 && detail.length <= MAX_DETAIL && !UNSAFE_TEXT.test(detail);

  // Solo segundos enteros: `parseInt("1.5")` daría 1 y una fecha HTTP daría un número cualquiera.
  const seconds = /^\d{1,3}$/.test(input.retryAfter ?? "") ? Number(input.retryAfter) : 0;
  const retryAfter = seconds > 0 && seconds <= MAX_RETRY_AFTER ? seconds : undefined;

  const message = showable ? detail : (BY_STATUS[input.status] ?? (input.status >= 500 ? UNAVAILABLE : GENERIC));

  const client = input.status >= 400 && input.status < 500;
  const rawField = body["field"];
  const field = client && typeof rawField === "string" && FIELDS.has(rawField) ? rawField : undefined;
  const rawChecks = body["failed_checks"];
  const failedChecks = client && Array.isArray(rawChecks) ? [...new Set(rawChecks.filter(isCheckCode))] : [];
  const rawErrors = body["errors"];
  const invalidFields =
    client && code === "validation_error" && Array.isArray(rawErrors)
      ? [
          ...new Set(
            rawErrors.flatMap((entry: unknown) => {
              const loc = typeof entry === "object" && entry !== null ? (entry as Record<string, unknown>)["loc"] : undefined;
              const name = typeof loc === "string" ? FIELD_LOCS.get(loc) : undefined;
              return name === undefined ? [] : [name];
            }),
          ),
        ]
      : [];

  // `fields` de un problema de campos: solo nombres de una lista cerrada y textos cortos y seguros; nada más se refleja.
  const rawFields = body["fields"];
  const fieldsOf = (allowed: ReadonlySet<string>): { field: string; message: string }[] =>
    Array.isArray(rawFields)
      ? rawFields.flatMap((entry: unknown) => {
          if (typeof entry !== "object" || entry === null) return [];
          const { field: name, message: text } = entry as Record<string, unknown>;
          if (typeof name !== "string" || !allowed.has(name)) return [];
          if (typeof text !== "string" || text.length === 0 || text.length > MAX_DETAIL || UNSAFE_TEXT.test(text)) return [];
          return [{ field: name, message: text }];
        })
      : [];
  const profileFields = client && code === "invalid_profile" ? fieldsOf(PROFILE_FIELD_SET) : [];
  const clientFields = client && code === "invalid_client" ? fieldsOf(CLIENT_FIELD_SET) : [];

  return {
    status: input.status,
    code,
    message,
    ...(retryAfter ? { retryAfter } : {}),
    ...(field ? { field } : {}),
    ...(failedChecks.length > 0 ? { failedChecks } : {}),
    ...(invalidFields.length > 0 ? { invalidFields } : {}),
    ...(profileFields.length > 0 ? { profileFields } : {}),
    ...(clientFields.length > 0 ? { clientFields } : {}),
  };
}

export const SERVICE_UNAVAILABLE: Problem = { status: 503, code: "service_unavailable", message: UNAVAILABLE };
