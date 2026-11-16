// Lógica del Route Handler `POST /asistente/enviar` (SPEC-W-004 §5.5, D-02): reenvía el mensaje a `POST /api/chat` de la API con el token de la sesión y
// devuelve su flujo `text/event-stream` SIN acumularlo. El navegador no tiene el JWT: la sesión se lee de las cookies. A diferencia de las Server Actions,
// Next no comprueba el origen de un Route Handler: se comprueba aquí (defensa CSRF).
//
// Sin alias ni `server-only`: las dependencias (token, URL de la API y `fetch`) se inyectan para que lo ejecuten directamente los tests. El Route Handler
// (`app/(app)/asistente/enviar/route.ts`) pone las reales.
import { SERVICE_UNAVAILABLE, describeProblem, type Problem } from "./problems.ts";
import { isSameOrigin, originHeaders } from "./same-origin.ts";
import { MAX_MESSAGE_CHARS, SESSION_EXPIRED, isUuid } from "./chat.ts";

export type ChatHandlerDeps = {
  token: () => Promise<string | null>;
  backend: () => string;
  fetch: (input: string, init: RequestInit) => Promise<Response>;
};

const MAX_BODY_BYTES = 20 * 1024; // el cuerpo legítimo son ≤ 2.000 caracteres y un uuid
const MAX_PROBLEM_BYTES = 16 * 1024;
const NO_STORE = { "cache-control": "no-store" };

// `no-transform` evita que la compresión de `next start` acumule el flujo; `x-accel-buffering` lo mismo para nginx y similares.
const STREAM_HEADERS = {
  "content-type": "text/event-stream; charset=utf-8",
  "cache-control": "private, no-store, no-transform",
  "x-accel-buffering": "no",
};

type SendBody = { conversation_id: string | null; content: string };

/** El cuerpo, o `null` si no es lo que se espera. El texto no se recorta ni se valida aquí: eso lo decide la API (mensaje vacío o demasiado largo). */
export function parseSendBody(text: string): SendBody | null {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const { conversation_id: conversationId = null, content } = value as Record<string, unknown>;
  if (typeof content !== "string" || content.length > MAX_MESSAGE_CHARS * 4) return null;
  if (conversationId !== null && !isUuid(conversationId)) return null;
  return { conversation_id: conversationId, content };
}

function reply(problem: Problem, extra: Record<string, unknown> = {}): Response {
  const { status, code, message, retryAfter } = problem;
  return Response.json({ code, message, ...extra }, { status, headers: { ...NO_STORE, ...(retryAfter ? { "retry-after": String(retryAfter) } : {}) } });
}

async function readBody(request: Request): Promise<string | null> {
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return null;
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY_BYTES) {
      await reader.cancel().catch(() => undefined);
      return null;
    }
    chunks.push(value);
  }
  const joined = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(joined);
}

async function problemBody(upstream: Response): Promise<unknown> {
  try {
    const text = await upstream.text();
    return text.length <= MAX_PROBLEM_BYTES ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

export async function handleSend(request: Request, deps: ChatHandlerDeps): Promise<Response> {
  if (!isSameOrigin(originHeaders(request.headers))) {
    return reply({ status: 403, code: "forbidden", message: "Esta petición no se admite desde otro sitio." });
  }
  const text = await readBody(request);
  const body = text === null ? null : parseSendBody(text);
  if (body === null) return reply({ status: 422, code: "invalid_request", message: "No hemos entendido el mensaje. Recarga la página e inténtalo de nuevo." });

  const token = await deps.token();
  if (!token) return reply({ status: 401, code: "session", message: SESSION_EXPIRED });

  let upstream: Response;
  try {
    upstream = await deps.fetch(`${deps.backend()}/api/chat`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify(body),
      // El corte del navegador llega hasta la API: ella guarda lo recibido como «interrumpido» y cierra la conexión con el agente.
      signal: request.signal,
      cache: "no-store",
      redirect: "manual",
    } as RequestInit);
  } catch {
    return reply(SERVICE_UNAVAILABLE);
  }

  const isStream = upstream.status === 200 && (upstream.headers.get("content-type") ?? "").toLowerCase().startsWith("text/event-stream") && upstream.body !== null;
  if (isStream && upstream.body) {
    const headers: Record<string, string> = { ...STREAM_HEADERS };
    const requestId = upstream.headers.get("x-request-id");
    if (requestId && /^[A-Za-z0-9_-]{8,64}$/.test(requestId)) headers["x-request-id"] = requestId;
    return new Response(upstream.body, { status: 200, headers });
  }

  // Un fallo ANTES del primer frame: es un problem+json de la API; se traduce a lo que ve la persona.
  const problemJson = upstream.status >= 400 && upstream.status < 600 ? await problemBody(upstream) : null;
  await upstream.body?.cancel().catch(() => undefined);
  if (upstream.status < 400 || upstream.status >= 600) return reply(SERVICE_UNAVAILABLE); // 200 que no es un flujo, o una redirección: no es de fiar
  const problem = describeProblem({ status: upstream.status, body: problemJson, retryAfter: upstream.headers.get("retry-after") });
  // La API rechazó el token: para el navegador es «sesión caducada».
  if (upstream.status === 401) return reply({ ...problem, code: "session", message: SESSION_EXPIRED });
  const conversationId =
    typeof problemJson === "object" && problemJson !== null && !Array.isArray(problemJson) ? (problemJson as Record<string, unknown>)["conversation_id"] : undefined;
  return reply(problem, isUuid(conversationId) ? { conversation_id: conversationId } : {});
}
