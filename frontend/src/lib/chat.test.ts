// El lector del flujo, el estado de la respuesta y los textos del asistente (SPEC-W-004 §5.5, AC-02, AC-18, AC-22).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  ChatEventParser,
  ChatStreamError,
  MAX_MESSAGE_CHARS,
  NOTICE,
  REASONS,
  applyEvent,
  canSend,
  counterText,
  decodeEvent,
  formatValidAsOf,
  fromApi,
  fromReply,
  interrupted,
  isReason,
  isUuid,
  linkHref,
  noteFor,
  readChatStream,
  referralLine,
  startReply,
  userMessage,
  type ChatEvent,
} from "./chat.ts";

const CONVERSATION = "0b0d0a2e-7a66-4c6f-9b0e-1d3a5c7e9f11";
const USER_MESSAGE = "11111111-2222-4333-8444-555555555555";
const MESSAGE = "66666666-7777-4888-8999-aaaaaaaaaaaa";
const EXAMPLES = ["answer_with_citation", "answer_with_tool", "answer_length", "abstention_professional", "abstention_no_source", "abstention_out_of_scope", "error_upstream", "error_tool"];

/** Lo que el servidor reenvía al navegador a partir de un ejemplo del contrato C2: `start` delante, `usage` sin coste y `done` y `error` con sus identificadores. */
function browserStream(name: string): string {
  const raw = readFileSync(new URL(`../../../contracts/examples/chat/${name}.sse`, import.meta.url), "utf-8");
  const blocks = raw.split("\n\n").filter((block) => block.trim() !== "");
  const out = [`event: start\ndata: ${JSON.stringify({ conversation_id: CONVERSATION, user_message_id: USER_MESSAGE, message_id: MESSAGE })}\n\n`];
  for (const block of blocks) {
    const [eventLine = "", dataLine = ""] = block.split("\n");
    const event = eventLine.slice("event: ".length);
    const data = JSON.parse(dataLine.slice("data: ".length)) as Record<string, unknown>;
    if (event === "usage") delete data["cost_eur"];
    if (event === "done") Object.assign(data, { message_id: MESSAGE, has_source: data["finish_reason"] === "abstained" ? null : true, status: data["finish_reason"] === "abstained" ? "abstained" : "complete" });
    if (event === "error") Object.assign(data, { message: "Texto fijo del servidor.", message_id: MESSAGE });
    out.push(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  }
  return out.join("");
}

function parseAll(...chunks: string[]): ChatEvent[] {
  const parser = new ChatEventParser();
  const events: ChatEvent[] = [];
  for (const chunk of chunks) events.push(...parser.feed(chunk));
  events.push(...parser.finish());
  return events;
}

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${typeof data === "string" ? data : JSON.stringify(data)}\n\n`;
const TOKEN = (delta: string) => sse("token", { delta });
const DONE = sse("done", { finish_reason: "stop", trace_id: "t", message_id: MESSAGE, has_source: true, status: "complete" });

// --- El lector: el troceado de la red no cambia lo que se lee ------------------------------------------------------------------------

for (const name of EXAMPLES) {
  test(`cualquier corte en dos del flujo «${name}» da los mismos eventos`, () => {
    const text = browserStream(name);
    const whole = parseAll(text);
    assert.ok(whole.length >= 2, name);
    assert.equal(whole[0]?.event, "start");
    assert.ok(["done", "error"].includes(whole.at(-1)?.event ?? ""), name);
    for (let cut = 0; cut <= text.length; cut++) assert.deepEqual(parseAll(text.slice(0, cut), text.slice(cut)), whole, `${name} @${cut}`);
  });

  test(`«${name}» carácter a carácter, con \\r\\n y con \\r da lo mismo`, () => {
    const text = browserStream(name);
    const whole = parseAll(text);
    assert.deepEqual(parseAll(...text.split("")), whole);
    assert.deepEqual(parseAll(text.replaceAll("\n", "\r\n")), whole);
    assert.deepEqual(parseAll(...text.replaceAll("\n", "\r\n").split("")), whole);
    assert.deepEqual(parseAll(text.replaceAll("\n", "\r")), whole);
    assert.deepEqual(parseAll(...text.replaceAll("\n", "\r").split("")), whole);
  });
}

test("los comentarios, los latidos y los campos desconocidos se ignoran", () => {
  const text = `: ping\n\nid: 7\nretry: 3000\nevent: token\n: otro\ndata: {"delta":"hola"}\nfoo: bar\n\n${DONE}`;
  assert.deepEqual(parseAll(text).map((e) => e.event), ["token", "done"]);
});

test("un evento desconocido se descarta, también su contenido, y no afecta a los demás", () => {
  const events = parseAll(`event: ping\ndata: SECRETO que no es JSON\n\nevent: message\ndata: {"delta":"x"}\n\ndata: sin nombre\n\n${TOKEN("a")}${DONE}`);
  assert.deepEqual(events.map((e) => e.event), ["token", "done"]);
});

test("tras el primer `done` o `error` no se admite nada más", () => {
  for (const terminal of [DONE, sse("error", { code: "timeout", message: "Fijo.", message_id: MESSAGE })]) {
    const parser = new ChatEventParser();
    const first = parser.feed(`${TOKEN("a")}${terminal}${TOKEN("tarde")}${DONE}`);
    assert.deepEqual(first.map((e) => e.event), ["token", terminal === DONE ? "done" : "error"]);
    assert.equal(parser.ended, true);
    assert.deepEqual(parser.feed(TOKEN("más tarde")), []);
    assert.deepEqual(parser.finish(), []);
  }
});

test("un flujo que se cierra sin terminal no está terminado y deja lo pendiente a la vista", () => {
  const parser = new ChatEventParser();
  parser.feed(`${TOKEN("a")}event: token\ndata: {"del`);
  assert.equal(parser.ended, false);
  assert.equal(parser.pending, true);
  assert.equal(new ChatEventParser().pending, false);
});

test("los saltos de línea dentro de un texto no parten el evento", () => {
  const delta = "línea 1\nlínea 2\r\ndata: falso\n\nevent: done";
  assert.deepEqual(parseAll(TOKEN(delta)), [{ event: "token", data: { delta } }]);
});

test("`data:` en varias líneas se une con saltos y un solo espacio tras los dos puntos se quita", () => {
  assert.deepEqual(parseAll('event: token\ndata: {"delta":\ndata:  "a"}\n\n'), [{ event: "token", data: { delta: "a" } }]);
});

// --- El lector: lo que no vale se rechaza -----------------------------------------------------------------------------------------------

test("una línea o un evento desmesurados lanzan un error y no crecen sin fin", () => {
  assert.throws(() => parseAll(`data: ${"a".repeat(40_000)}\n\n`), (e) => e instanceof ChatStreamError && e.reason === "line_too_long");
  assert.throws(() => new ChatEventParser().feed("a".repeat(40_000)), (e) => e instanceof ChatStreamError && e.reason === "line_too_long");
  const lines = Array.from({ length: 5 }, () => `data: ${"b".repeat(20_000)}\n`).join("");
  assert.throws(() => parseAll(`event: token\n${lines}\n`), (e) => e instanceof ChatStreamError && e.reason === "event_too_long");
  // El tope es por línea y por evento: varias líneas dentro del tope pasan.
  assert.doesNotThrow(() => parseAll(`event: ping\ndata: ${"c".repeat(30_000)}\n\n`));
});

const BAD = [
  ["token", "no es json"],
  ["token", "[]"],
  ["token", "null"],
  ["token", "{}"],
  ["token", '{"delta":5}'],
  ["start", { conversation_id: "no-uuid", user_message_id: USER_MESSAGE, message_id: MESSAGE }],
  ["citation", { id: "1", title: "t", publisher: "p" }],
  ["citation", { id: 1, title: "t", publisher: "p", url: "https://x.example", valid_as_of: null }],
  ["tool_call", { name: "a", status: "raro" }],
  ["abstention", { reason: "otra", referral: null }],
  ["abstention", { reason: "no_source", referral: "fiscalista" }],
  ["usage", { input_tokens: "5", output_tokens: 1 }],
  ["usage", { input_tokens: -1, output_tokens: 1 }],
  ["done", { finish_reason: "stop", trace_id: "t" }],
  ["done", { finish_reason: "stop", trace_id: "t", message_id: MESSAGE, has_source: "sí", status: "complete" }],
  ["done", { finish_reason: "stop", trace_id: "t", message_id: MESSAGE, has_source: true, status: "rara" }],
  ["error", { code: "x" }],
] as const;

for (const [name, data] of BAD) {
  test(`un evento «${name}» que no cumple la forma lanza un error sin reflejar sus datos: ${typeof data === "string" ? data : JSON.stringify(data).slice(0, 50)}`, () => {
    assert.throws(
      () => parseAll(sse(name, data)),
      (e) => e instanceof ChatStreamError && e.reason === "invalid_event" && !e.message.includes("no es json"),
    );
  });
}

test("decodeEvent acepta la forma de cada uno de los ocho eventos y descarta el resto", () => {
  assert.equal(decodeEvent("nada", "{}"), null);
  assert.equal(decodeEvent("TOKEN", '{"delta":"x"}'), null);
  assert.deepEqual(decodeEvent("start", JSON.stringify({ conversation_id: CONVERSATION, user_message_id: USER_MESSAGE, message_id: MESSAGE })), {
    event: "start",
    data: { conversation_id: CONVERSATION, user_message_id: USER_MESSAGE, message_id: MESSAGE },
  });
  assert.deepEqual(decodeEvent("citation", '{"id":"1","title":"t","publisher":"BOE","url":"https://www.boe.es/a","valid_as_of":"2026-09-01"}'), {
    event: "citation",
    data: { id: "1", title: "t", publisher: "BOE", url: "https://www.boe.es/a", valid_as_of: "2026-09-01", quote: null },
  });
  assert.deepEqual(decodeEvent("abstention", '{"reason":"out_of_scope","referral":null}'), { event: "abstention", data: { reason: "out_of_scope", referral: null } });
  assert.deepEqual(decodeEvent("error", '{"code":"timeout","message":"Fijo."}'), { event: "error", data: { code: "timeout", message: "Fijo.", message_id: null } });
});

// --- Leer un cuerpo de verdad (ReadableStream) ----------------------------------------------------------------------------------------

function bodyOf(text: string, size: number): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return new ReadableStream({
    pull(controller) {
      if (offset >= bytes.length) return controller.close();
      controller.enqueue(bytes.slice(offset, offset + size));
      offset += size;
    },
  });
}

test("readChatStream entrega los eventos aunque un carácter de varios bytes llegue partido", async () => {
  const text = `${TOKEN("Inversión «sujeto pasivo» €")}${DONE}`;
  for (const size of [1, 2, 3, 7, 1000]) {
    const seen: ChatEvent[] = [];
    assert.equal(await readChatStream(bodyOf(text, size), (e) => seen.push(e)), "terminal");
    assert.equal(seen[0]?.event === "token" && seen[0].data.delta, "Inversión «sujeto pasivo» €");
  }
});

test("readChatStream devuelve `closed` si el flujo se cierra sin `done` ni `error`, y lo recibido se entrega", async () => {
  const seen: ChatEvent[] = [];
  assert.equal(await readChatStream(bodyOf(TOKEN("a") + TOKEN("b"), 5), (e) => seen.push(e)), "closed");
  assert.deepEqual(seen.map((e) => e.event), ["token", "token"]);
  assert.equal(await readChatStream(bodyOf("", 5), () => undefined), "closed");
});

test("readChatStream no acepta UTF-8 inválido ni un flujo malformado", async () => {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new Uint8Array([0x65, 0x76, 0xff, 0xfe]));
      controller.close();
    },
  });
  await assert.rejects(readChatStream(body, () => undefined), (e) => e instanceof ChatStreamError);
  await assert.rejects(readChatStream(bodyOf(sse("token", "esto no es json"), 4), () => undefined), (e) => e instanceof ChatStreamError && e.reason === "invalid_event");
});

test("readChatStream: «Detener» cancela la lectura y sube un AbortError, no un flujo cerrado", async () => {
  const controller = new AbortController();
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(new TextEncoder().encode(TOKEN("a")));
    },
    cancel() {
      cancelled = true;
    },
  });
  const seen: ChatEvent[] = [];
  const pending = readChatStream(
    body,
    (event) => {
      seen.push(event);
      controller.abort();
    },
    controller.signal,
  );
  await assert.rejects(pending, (e) => e instanceof DOMException && e.name === "AbortError");
  assert.equal(seen.length, 1);
  assert.equal(cancelled, true);
});

test("readChatStream cancela el origen al terminar (no deja la conexión abierta)", async () => {
  let cancelled = false;
  const text = new TextEncoder().encode(`${TOKEN("a")}${DONE}${TOKEN("tarde")}`);
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(text);
    },
    cancel() {
      cancelled = true;
    },
  });
  assert.equal(await readChatStream(body, () => undefined), "terminal");
  assert.equal(cancelled, true);
});

// --- El estado de la respuesta -----------------------------------------------------------------------------------------------------------

function reduce(text: string) {
  return parseAll(text).reduce(applyEvent, startReply());
}

test("una respuesta con cita termina completa con fuente y su texto es el de los tokens", () => {
  const reply = reduce(browserStream("answer_with_citation"));
  assert.equal(reply.terminal, "done");
  assert.equal(reply.status, "complete");
  assert.equal(reply.hasSource, true);
  assert.equal(reply.messageId, MESSAGE);
  assert.equal(reply.text, "Si el cliente es una empresa de la UE con NIF-IVA válido, la factura va sin IVA y debe incluir la mención «Inversión del sujeto pasivo» [1].");
  assert.equal(reply.citations[0]?.publisher, "BOE");
  assert.deepEqual(reply.usage, { input_tokens: 2410, output_tokens: 96 });
});

test("una abstención guarda la derivación y termina abstenida; una herramienta en curso se apaga al terminar", () => {
  const reply = reduce(browserStream("abstention_professional"));
  assert.equal(reply.status, "abstained");
  assert.deepEqual(reply.abstention, { reason: "professional_judgment", referral: "gestor" });
  const tool = parseAll(browserStream("answer_with_tool"));
  const during = tool.slice(0, 2).reduce(applyEvent, startReply());
  assert.equal(during.tool, "buscar_facturas");
  assert.equal(tool.reduce(applyEvent, startReply()).tool, null);
});

test("un error del flujo lleva el texto fijo del servidor y deja el mensaje guardado a mano", () => {
  const reply = reduce(browserStream("error_upstream"));
  assert.equal(reply.terminal, "error");
  assert.equal(reply.status, "error");
  assert.deepEqual(reply.error, { code: "upstream_error", message: "Texto fijo del servidor." });
  assert.equal(reply.messageId, MESSAGE);
});

test("nada que llegue después del terminal cambia la respuesta", () => {
  const done = reduce(`${TOKEN("a")}${DONE}`);
  assert.equal(applyEvent(done, { event: "token", data: { delta: "tarde" } }), done);
  assert.equal(applyEvent(done, { event: "citation", data: { id: "9", title: "t", publisher: "p", url: "https://x.example", valid_as_of: null, quote: null } }), done);
});

test("el texto se acota a 8.000 caracteres, las citas a 20 y manda la primera abstención", () => {
  let reply = startReply();
  for (let i = 0; i < 5; i++) reply = applyEvent(reply, { event: "token", data: { delta: "a".repeat(2000) } });
  assert.equal(reply.text.length, 8000);
  for (let i = 0; i < 25; i++) reply = applyEvent(reply, { event: "citation", data: { id: String(i), title: "t", publisher: "p", url: "https://x.example", valid_as_of: null, quote: null } });
  assert.equal(reply.citations.length, 20);
  reply = applyEvent(reply, { event: "abstention", data: { reason: "no_source", referral: "asesor" } });
  reply = applyEvent(reply, { event: "abstention", data: { reason: "out_of_scope", referral: null } });
  assert.deepEqual(reply.abstention, { reason: "no_source", referral: "asesor" });
});

test("cortar el flujo deja lo recibido marcado como interrumpido y una respuesta terminada no cambia", () => {
  const partial = reduce(`${TOKEN("Empiezo")}`);
  const cut = interrupted(partial);
  assert.equal(cut.status, "interrupted");
  assert.equal(cut.text, "Empiezo");
  const message = fromReply(cut, "local-1");
  assert.equal(message.status, "interrupted");
  assert.equal(message.saved, false); // el servidor tarda un instante en guardarla: todavía no se puede valorar
  const finished = reduce(`${TOKEN("a")}${DONE}`);
  assert.equal(interrupted(finished), finished);
  assert.equal(fromReply(finished, "local-2").saved, true);
  assert.equal(fromReply(finished, "local-2").id, MESSAGE);
});

test("cada estado de una respuesta tiene su nota", () => {
  const base = fromReply(reduce(`${TOKEN("a")}${DONE}`), "x");
  assert.equal(noteFor(base), null);
  assert.equal(noteFor({ ...base, hasSource: false })?.kind, "no_source");
  assert.equal(noteFor({ ...base, hasSource: null }), null);
  assert.equal(noteFor({ ...base, status: "interrupted" })?.kind, "interrupted");
  assert.equal(noteFor({ ...base, status: "abstained", hasSource: false }), null); // una abstención no se avisa como «sin fuente»
  assert.equal(noteFor({ ...base, status: "error", errorMessage: "Fijo." })?.text, "Fijo.");
  assert.match(noteFor({ ...base, status: "error" })?.text ?? "", /no ha podido terminar/);
  assert.equal(noteFor(userMessage("u", "hola", true)), null);
});

test("fromApi normaliza lo que viene de la API: motivo desconocido fuera, citas acotadas y sin `quote` = nulo", () => {
  const message = fromApi({
    id: MESSAGE,
    role: "assistant",
    content: "<b>hola</b>",
    status: "complete",
    has_source: true,
    citations: Array.from({ length: 30 }, (_, i) => ({ id: String(i), title: "t", publisher: "p", url: "https://x.example", valid_as_of: null })),
    abstention: null,
    rating: "down",
    reason: "otro-motivo-raro",
  });
  assert.equal(message.content, "<b>hola</b>"); // texto: se pinta escapado, no se interpreta
  assert.equal(message.citations.length, 20);
  assert.equal(message.citations[0]?.quote, null);
  assert.equal(message.reason, null);
  assert.equal(message.rating, "down");
  assert.equal(message.saved, true);
  assert.equal(fromApi({ ...{ id: MESSAGE, role: "user" as const, content: "x", status: "complete" as const, citations: [], abstention: null }, reason: "incorrect" }).reason, "incorrect");
});

// --- Enlaces, fechas y textos ------------------------------------------------------------------------------------------------------------

test("solo una URL https con host se enseña como enlace", () => {
  assert.equal(linkHref("https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696"), "https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696");
  assert.equal(linkHref("HTTPS://WWW.BOE.ES/a"), "https://www.boe.es/a");
  assert.equal(linkHref("https:///a"), "https://a/"); // el analizador de URLs lo normaliza: lo que se enlaza es lo normalizado, siempre https y con host
  for (const bad of ["http://www.boe.es/a", "javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,<script>1</script>", "//www.boe.es/a", "https://", "", "   ", "boe.es", "ftp://x.example", "vbscript:x", "https://user:clave@www.boe.es/a", "https://user@www.boe.es/a", "file:///etc/passwd"]) {
    assert.equal(linkHref(bad), null, JSON.stringify(bad));
  }
});

test("la vigencia se dice en español y una fecha que no es fecha se omite", () => {
  assert.equal(formatValidAsOf("2026-09-01"), "1 de septiembre de 2026");
  assert.equal(formatValidAsOf("2026-12-31"), "31 de diciembre de 2026");
  for (const bad of [null, "", "01/09/2026", "2026-13-01", "2026-02-30x", "ayer"]) assert.equal(formatValidAsOf(bad), null, String(bad));
});

test("se puede enviar de 1 a 2.000 caracteres sin contar los espacios de los extremos, y no mientras se responde", () => {
  assert.equal(canSend("", false), false);
  assert.equal(canSend("  \n ", false), false);
  assert.equal(canSend("a", false), true);
  assert.equal(canSend("a".repeat(MAX_MESSAGE_CHARS), false), true);
  assert.equal(canSend("  " + "a".repeat(MAX_MESSAGE_CHARS) + "  ", false), true);
  assert.equal(canSend("a".repeat(MAX_MESSAGE_CHARS + 1), false), false);
  assert.equal(canSend("hola", true), false);
});

test("el contador dice cuántos caracteres hay y cuántos sobran", () => {
  assert.equal(counterText(""), "0 de 2000 caracteres");
  assert.equal(counterText("  hola  "), "4 de 2000 caracteres");
  assert.equal(counterText("a".repeat(2000)), "2000 de 2000 caracteres");
  assert.equal(counterText("a".repeat(2003)), "Te pasas 3 caracteres (máximo 2000)");
});

test("la derivación y el aviso son los textos fijos de la spec (D-09, D-11)", () => {
  assert.equal(referralLine("gestor"), "Para tu caso, consúltalo con tu gestor.");
  assert.equal(referralLine("asesor"), "Para tu caso, consúltalo con un asesor.");
  assert.equal(referralLine(null), null);
  assert.equal(NOTICE, "Cuadre orienta, no asesora. Para decidir sobre tu caso, consulta a tu gestor o a un asesor.");
});

test("los motivos de valoración son la lista cerrada del servidor", () => {
  assert.deepEqual(REASONS.map((r) => r.value), ["incorrect", "no_source", "not_helpful", "other"]);
  for (const reason of REASONS) assert.equal(isReason(reason.value), true);
  for (const bad of ["", "malo", null, undefined, 3, "Incorrect"]) assert.equal(isReason(bad), false, String(bad));
});

test("isUuid acepta solo un uuid", () => {
  assert.equal(isUuid(CONVERSATION), true);
  for (const bad of ["", "no-uuid", `${CONVERSATION}x`, ` ${CONVERSATION}`, null, undefined, 1, "../../x"]) assert.equal(isUuid(bad), false, String(bad));
});
