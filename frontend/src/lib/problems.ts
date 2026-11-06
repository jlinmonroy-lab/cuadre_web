// Errores de la API (`application/problem+json`, SPEC-W-001 §5.1) → lo que ve la persona. Puro: lo ejecutan directamente los tests.
//
// Los `detail` de la API ya vienen en español y sin datos, pero llegan por la red: solo se enseñan si son texto corto de un error
// 4xx. Un 5xx nunca enseña su cuerpo (podría llevar rutas o trazas de un servicio intermedio).

export type Problem = { status: number; code: string; message: string; retryAfter?: number };

const BY_STATUS: Record<number, string> = {
  401: "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.",
  403: "Tu cuenta no tiene permiso para hacer esto.",
  404: "No encontramos ese documento.",
};
const UNAVAILABLE = "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.";
const GENERIC = "No hemos podido completar la operación. Inténtalo de nuevo.";

const CODE = /^[a-z][a-z0-9_]{0,63}$/;
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
  return { status: input.status, code, message, ...(retryAfter ? { retryAfter } : {}) };
}

export const SERVICE_UNAVAILABLE: Problem = { status: 503, code: "service_unavailable", message: UNAVAILABLE };
