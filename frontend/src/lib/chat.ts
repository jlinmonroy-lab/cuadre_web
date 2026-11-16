// El asistente (SPEC-W-004 §5.5). Puro y sin alias: lo ejecutan directamente los tests (`node --test`).
//
// Todo lo que llega del flujo es dato no confiable (ADR-0012, D-10): se valida cada evento, se acotan las líneas y los eventos, se descarta
// lo desconocido y lo que venga después de `done`/`error`, y cada texto se pinta como TEXTO PLANO (nunca como HTML ni como Markdown). Solo una URL
// `https` con host se enseña como enlace.

export const MAX_MESSAGE_CHARS = 2000; // D-12: lo mismo que `cuadre.chat.limits.MAX_MESSAGE_CHARS`
export const MAX_LINE_CHARS = 32_768;
export const MAX_EVENT_CHARS = 65_536;
export const MAX_REPLY_CHARS = 8000; // lo que el servidor guarda de una respuesta: si llegara más, es un flujo que no es el nuestro

// --- Textos fijos (un solo sitio) --------------------------------------------------------------------------------------------------

/** D-09: el aviso permanente de no asesoramiento (RES-05). Provisional hasta cerrar CONF-003. */
export const NOTICE = "Cuadre orienta, no asesora. Para decidir sobre tu caso, consulta a tu gestor o a un asesor.";
export const NO_SOURCE_NOTE = "Esta respuesta no cita ninguna fuente oficial: tómala solo como orientación.";
export const INTERRUPTED_NOTE = "Respuesta interrumpida: esto es lo que llegó antes de cortarse.";
export const CONNECTION_LOST = "Se ha cortado la conexión con el asistente.";
export const SESSION_EXPIRED = "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.";
export const EMPTY_THREAD = "Aún no has preguntado nada. Escribe tu duda abajo y te respondo con fuentes oficiales.";

export function referralLine(referral: "gestor" | "asesor" | null): string | null {
  if (referral === "gestor") return "Para tu caso, consúltalo con tu gestor.";
  if (referral === "asesor") return "Para tu caso, consúltalo con un asesor.";
  return null;
}

export const REASONS = [
  { value: "incorrect", label: "Es incorrecta" },
  { value: "no_source", label: "No cita una fuente" },
  { value: "not_helpful", label: "No me ayuda" },
  { value: "other", label: "Otro motivo" },
] as const;
export type FeedbackReason = (typeof REASONS)[number]["value"];
export type Rating = "up" | "down";

export function isReason(value: unknown): value is FeedbackReason {
  return REASONS.some((reason) => reason.value === value);
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

// --- Lo que se escribe -------------------------------------------------------------------------------------------------------------

/** ¿Se puede enviar? El texto cuenta sin los espacios de los extremos, como en el servidor. */
export function canSend(text: string, busy: boolean): boolean {
  const length = text.trim().length;
  return !busy && length >= 1 && length <= MAX_MESSAGE_CHARS;
}

export function counterText(text: string): string {
  const length = text.trim().length;
  return length > MAX_MESSAGE_CHARS ? `Te pasas ${length - MAX_MESSAGE_CHARS} caracteres (máximo ${MAX_MESSAGE_CHARS})` : `${length} de ${MAX_MESSAGE_CHARS} caracteres`;
}

// --- Citas -------------------------------------------------------------------------------------------------------------------------

/** El enlace de una cita, o `null` si no se puede enseñar como enlace: solo `https:` con host y sin credenciales (D-10). */
export function linkHref(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" || parsed.hostname === "" || parsed.username !== "" || parsed.password !== "") return null;
    return parsed.href;
  } catch {
    return null;
  }
}

/** «1 de septiembre de 2026» a partir de `2026-09-01`; `null` si no es una fecha. Sin zona horaria: la fecha del documento no se desplaza. */
export function formatValidAsOf(iso: string | null): string | null {
  if (iso === null || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(date);
}

// --- Eventos del flujo (D-06) -----------------------------------------------------------------------------------------------------

export type Citation = { id: string; title: string; publisher: string; url: string; valid_as_of: string | null; quote: string | null };
export type Abstention = { reason: "no_source" | "professional_judgment" | "out_of_scope"; referral: "gestor" | "asesor" | null };
export type MessageStatus = "complete" | "abstained" | "error" | "interrupted";

export type ChatEvent =
  | { event: "start"; data: { conversation_id: string; user_message_id: string; message_id: string } }
  | { event: "token"; data: { delta: string } }
  | { event: "citation"; data: Citation }
  | { event: "tool_call"; data: { name: string; status: "started" | "finished" | "failed" } }
  | { event: "abstention"; data: Abstention }
  | { event: "usage"; data: { input_tokens: number; output_tokens: number } }
  | { event: "done"; data: { finish_reason: string; trace_id: string; message_id: string; has_source: boolean | null; status: MessageStatus } }
  | { event: "error"; data: { code: string; message: string; message_id: string | null } };

export class ChatStreamError extends Error {
  readonly reason: "line_too_long" | "event_too_long" | "invalid_event" | "stream_too_long";

  constructor(reason: "line_too_long" | "event_too_long" | "invalid_event" | "stream_too_long") {
    super(reason);
    this.reason = reason;
  }
}

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json => typeof value === "object" && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === "string";
const isNullableString = (value: unknown): value is string | null => value === null || typeof value === "string";
const isCount = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0;
const STATUSES: readonly string[] = ["complete", "abstained", "error", "interrupted"];

/** Un evento ya parseado, o `null` si su nombre no es de los ocho (se descarta). Lanza `ChatStreamError` si lo es y sus datos no valen. */
export function decodeEvent(name: string, raw: string): ChatEvent | null {
  if (!["start", "token", "citation", "tool_call", "abstention", "usage", "done", "error"].includes(name)) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new ChatStreamError("invalid_event");
  }
  if (!isObject(data)) throw new ChatStreamError("invalid_event");
  const bad = () => new ChatStreamError("invalid_event");
  switch (name) {
    case "start":
      if (isUuid(data["conversation_id"]) && isUuid(data["user_message_id"]) && isUuid(data["message_id"])) {
        return { event: "start", data: { conversation_id: data["conversation_id"], user_message_id: data["user_message_id"], message_id: data["message_id"] } };
      }
      throw bad();
    case "token":
      if (isString(data["delta"])) return { event: "token", data: { delta: data["delta"] } };
      throw bad();
    case "citation":
      if (isString(data["id"]) && isString(data["title"]) && isString(data["publisher"]) && isString(data["url"]) && isNullableString(data["valid_as_of"] ?? null) && isNullableString(data["quote"] ?? null)) {
        return {
          event: "citation",
          data: { id: data["id"], title: data["title"], publisher: data["publisher"], url: data["url"], valid_as_of: (data["valid_as_of"] ?? null) as string | null, quote: (data["quote"] ?? null) as string | null },
        };
      }
      throw bad();
    case "tool_call":
      if (isString(data["name"]) && (data["status"] === "started" || data["status"] === "finished" || data["status"] === "failed")) {
        return { event: "tool_call", data: { name: data["name"], status: data["status"] } };
      }
      throw bad();
    case "abstention": {
      const reason = data["reason"];
      const referral = data["referral"] ?? null;
      if ((reason === "no_source" || reason === "professional_judgment" || reason === "out_of_scope") && (referral === null || referral === "gestor" || referral === "asesor")) {
        return { event: "abstention", data: { reason, referral } };
      }
      throw bad();
    }
    case "usage":
      if (isCount(data["input_tokens"]) && isCount(data["output_tokens"])) return { event: "usage", data: { input_tokens: data["input_tokens"], output_tokens: data["output_tokens"] } };
      throw bad();
    case "done": {
      const status = data["status"];
      const hasSource = data["has_source"] ?? null;
      if (isString(data["finish_reason"]) && isString(data["trace_id"]) && isString(data["message_id"]) && (hasSource === null || typeof hasSource === "boolean") && isString(status) && STATUSES.includes(status)) {
        return { event: "done", data: { finish_reason: data["finish_reason"], trace_id: data["trace_id"], message_id: data["message_id"], has_source: hasSource, status: status as MessageStatus } };
      }
      throw bad();
    }
    default:
      if (isString(data["code"]) && isString(data["message"]) && isNullableString(data["message_id"] ?? null)) {
        return { event: "error", data: { code: data["code"], message: data["message"], message_id: (data["message_id"] ?? null) as string | null } };
      }
      throw bad();
  }
}

/**
 * Trocea el texto del flujo (`text/event-stream`) en eventos. Incremental: `feed` recibe lo que va llegando (ya decodificado) y devuelve los eventos que
 * se completan. Una línea o un evento demasiado largos, o un evento conocido con datos que no valen, lanzan `ChatStreamError`; los eventos desconocidos
 * se descartan; tras el primer `done` o `error` no se admite nada más (`ended`).
 */
export class ChatEventParser {
  private buffer = "";
  private name = "";
  private data: string[] = [];
  private hasData = false;
  private eventChars = 0;
  private done = false;

  get ended(): boolean {
    return this.done;
  }

  /** ¿Quedó algo sin terminar? (una línea o un evento a medias) */
  get pending(): boolean {
    return this.buffer !== "" || this.hasData || this.name !== "";
  }

  feed(text: string): ChatEvent[] {
    if (this.done) return [];
    this.buffer += text;
    const events: ChatEvent[] = [];
    let position = 0;
    while (!this.done) {
      const found = this.nextBreak(position);
      if (found === null) {
        if (this.buffer.length - position > MAX_LINE_CHARS) throw new ChatStreamError("line_too_long");
        break;
      }
      const [index, length] = found;
      if (length === 1 && this.buffer[index] === "\r" && index === this.buffer.length - 1) {
        // Un `\r` al final del trozo puede ser el principio de `\r\n`: se espera al siguiente.
        if (index - position > MAX_LINE_CHARS) throw new ChatStreamError("line_too_long");
        break;
      }
      const line = this.buffer.slice(position, index);
      if (line.length > MAX_LINE_CHARS) throw new ChatStreamError("line_too_long");
      position = index + length;
      const event = this.line(line);
      if (event !== null) {
        events.push(event);
        if (event.event === "done" || event.event === "error") this.done = true;
      }
    }
    this.buffer = this.done ? "" : this.buffer.slice(position);
    return events;
  }

  /** Se acabó el flujo: un `\r` que esperaba su `\n` era un fin de línea completo. */
  finish(): ChatEvent[] {
    return this.buffer.endsWith("\r") ? this.feed("\n") : [];
  }

  private nextBreak(from: number): [number, number] | null {
    for (let index = from; index < this.buffer.length; index++) {
      const char = this.buffer[index];
      if (char === "\n") return [index, 1];
      if (char === "\r") return [index, this.buffer[index + 1] === "\n" ? 2 : 1];
    }
    return null;
  }

  private line(line: string): ChatEvent | null {
    if (line === "") return this.dispatch();
    if (line.startsWith(":")) return null; // latido
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    this.eventChars += line.length;
    if (this.eventChars > MAX_EVENT_CHARS) throw new ChatStreamError("event_too_long");
    if (field === "event") this.name = value;
    else if (field === "data") {
      this.data.push(value);
      this.hasData = true;
    }
    return null;
  }

  private dispatch(): ChatEvent | null {
    const name = this.name || "message";
    const raw = this.data.join("\n");
    const had = this.hasData;
    this.name = "";
    this.data = [];
    this.hasData = false;
    this.eventChars = 0;
    return had ? decodeEvent(name, raw) : null;
  }
}

/**
 * Lee un cuerpo de flujo hasta que termina, llamando a `onEvent` con cada evento. Devuelve `terminal` si llegó `done` o `error`, o `closed` si el flujo se cerró
 * sin ninguno (una respuesta interrumpida). Lanza `ChatStreamError` ante un flujo malformado o desmesurado. Si `signal` se aborta, la lectura se cancela y el
 * `AbortError` sube a quien llama.
 */
export async function readChatStream(body: ReadableStream<Uint8Array>, onEvent: (event: ChatEvent) => void, signal?: AbortSignal): Promise<"terminal" | "closed"> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const parser = new ChatEventParser();
  let received = 0;
  const onAbort = () => void reader.cancel().catch(() => undefined);
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        // `reader.cancel()` (por «Detener») termina la lectura como si el flujo hubiera acabado: no es lo mismo y no se confunde.
        if (signal?.aborted) throw new DOMException("La lectura se ha detenido.", "AbortError");
        for (const event of parser.feed(decoder.decode())) onEvent(event);
        for (const event of parser.finish()) onEvent(event);
        return parser.ended ? "terminal" : "closed";
      }
      received += value.byteLength;
      if (received > MAX_REPLY_CHARS * 64) throw new ChatStreamError("stream_too_long");
      let text: string;
      try {
        text = decoder.decode(value, { stream: true });
      } catch {
        throw new ChatStreamError("invalid_event");
      }
      for (const event of parser.feed(text)) onEvent(event);
      if (parser.ended) return "terminal";
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
    await reader.cancel().catch(() => undefined);
  }
}

// --- La respuesta que se está escribiendo -------------------------------------------------------------------------------------------

export type LiveReply = {
  messageId: string | null;
  text: string;
  citations: Citation[];
  abstention: Abstention | null;
  tool: string | null; // la herramienta que se está consultando ahora
  usage: { input_tokens: number; output_tokens: number } | null;
  terminal: "done" | "error" | null;
  status: MessageStatus | "streaming";
  finishReason: string | null;
  hasSource: boolean | null;
  error: { code: string; message: string } | null;
};

export function startReply(): LiveReply {
  return { messageId: null, text: "", citations: [], abstention: null, tool: null, usage: null, terminal: null, status: "streaming", finishReason: null, hasSource: null, error: null };
}

/** Aplica un evento a la respuesta en curso. No muta. Nada que llegue después del terminal cambia la respuesta. */
export function applyEvent(reply: LiveReply, event: ChatEvent): LiveReply {
  if (reply.terminal !== null) return reply;
  switch (event.event) {
    case "start":
      return { ...reply, messageId: event.data.message_id };
    case "token":
      return reply.text.length >= MAX_REPLY_CHARS ? reply : { ...reply, text: (reply.text + event.data.delta).slice(0, MAX_REPLY_CHARS) };
    case "citation":
      return reply.citations.length >= 20 ? reply : { ...reply, citations: [...reply.citations, event.data] };
    case "tool_call":
      return { ...reply, tool: event.data.status === "started" ? event.data.name : null };
    case "abstention":
      return reply.abstention === null ? { ...reply, abstention: event.data } : reply;
    case "usage":
      return { ...reply, usage: event.data };
    case "done":
      return { ...reply, terminal: "done", tool: null, messageId: event.data.message_id, status: event.data.status, finishReason: event.data.finish_reason, hasSource: event.data.has_source };
    case "error":
      return { ...reply, terminal: "error", tool: null, messageId: event.data.message_id ?? reply.messageId, status: "error", error: { code: event.data.code, message: event.data.message } };
  }
}

/** La respuesta cuando el flujo se corta sin terminal (el navegador lo detuvo, se perdió la conexión o el servidor lo cerró): lo recibido, marcado como interrumpido. */
export function interrupted(reply: LiveReply): LiveReply {
  return reply.terminal !== null ? reply : { ...reply, tool: null, status: "interrupted" };
}

// --- Un mensaje del hilo (lo que viene del servidor o de una respuesta ya terminada) -----------------------------------------------

export type ThreadMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: MessageStatus;
  hasSource: boolean | null;
  citations: Citation[];
  abstention: Abstention | null;
  rating: Rating | null;
  reason: FeedbackReason | null;
  /** `true` si el servidor ya tiene este mensaje y se puede valorar (una respuesta cortada por «Detener» tarda un instante en guardarse). */
  saved: boolean;
  /** Un texto de error del servidor (ya en español y fijo) si la respuesta terminó en `error`. */
  errorMessage: string | null;
};

export function fromReply(reply: LiveReply, fallbackId: string): ThreadMessage {
  const status: MessageStatus = reply.status === "streaming" ? "interrupted" : reply.status;
  return {
    id: reply.messageId ?? fallbackId,
    role: "assistant",
    content: reply.text,
    status,
    hasSource: reply.hasSource,
    citations: reply.citations,
    abstention: reply.abstention,
    rating: null,
    reason: null,
    saved: reply.terminal !== null,
    errorMessage: reply.error?.message ?? null,
  };
}

export function userMessage(id: string, content: string, saved: boolean): ThreadMessage {
  return { id, role: "user", content, status: "complete", hasSource: null, citations: [], abstention: null, rating: null, reason: null, saved, errorMessage: null };
}

/** Lo que dice una nota bajo la respuesta, según cómo terminó. */
export function noteFor(message: ThreadMessage): { kind: "interrupted" | "no_source" | "error"; text: string } | null {
  if (message.role !== "assistant") return null;
  if (message.status === "interrupted") return { kind: "interrupted", text: INTERRUPTED_NOTE };
  if (message.status === "error") return { kind: "error", text: message.errorMessage ?? "El asistente no ha podido terminar la respuesta." };
  if (message.status === "complete" && message.hasSource === false) return { kind: "no_source", text: NO_SOURCE_NOTE };
  return null;
}

/** El mensaje de la API de lista de conversaciones/hilos al modelo del hilo. La entrada viene de la API generada: se normaliza lo que no es de fiar. */
export function fromApi(message: {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: MessageStatus;
  has_source?: boolean | null;
  citations: (Omit<Citation, "quote"> & { quote?: string | null })[];
  abstention: Abstention | null;
  rating?: Rating | null;
  reason?: string | null;
}): ThreadMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,
    hasSource: message.has_source ?? null,
    citations: message.citations.slice(0, 20).map((citation) => ({ ...citation, quote: citation.quote ?? null })),
    abstention: message.abstention,
    rating: message.rating ?? null,
    reason: isReason(message.reason) ? message.reason : null,
    saved: true,
    errorMessage: null,
  };
}
