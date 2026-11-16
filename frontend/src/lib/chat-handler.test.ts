// El Route Handler del envío (SPEC-W-004 §5.5, D-02): origen, sesión, reenvío del flujo sin acumularlo y traducción de los fallos de la API (AC-02, AC-14, AC-20).
import assert from "node:assert/strict";
import { test } from "node:test";

import { handleSend, parseSendBody, type ChatHandlerDeps } from "./chat-handler.ts";

const TOKEN = "jwt-de-la-sesion-que-el-navegador-no-debe-ver";
const CONVERSATION = "0b0d0a2e-7a66-4c6f-9b0e-1d3a5c7e9f11";
const BACKEND = "http://127.0.0.1:8000";

type Call = { url: string; init: RequestInit };

function setup(upstream: () => Response | Promise<Response>, token: string | null = TOKEN) {
  const calls: Call[] = [];
  const counts = { token: 0 };
  const deps: ChatHandlerDeps = {
    token: async () => {
      counts.token += 1;
      return token;
    },
    backend: () => BACKEND,
    fetch: async (url, init) => {
      calls.push({ url, init });
      return upstream();
    },
  };
  return { deps, calls, counts };
}

function post(body: unknown, headers: Record<string, string> = { "sec-fetch-site": "same-origin" }): Request {
  return new Request("http://localhost:3000/asistente/enviar", {
    method: "POST",
    headers: { "content-type": "application/json", host: "localhost:3000", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

const stream = (chunks: string[]) =>
  new Response(new ReadableStream<Uint8Array>({ start(c) { for (const chunk of chunks) c.enqueue(new TextEncoder().encode(chunk)); c.close(); } }), {
    status: 200,
    headers: { "content-type": "text/event-stream; charset=utf-8" },
  });

const problem = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/problem+json", ...headers } });

const OK_BODY = { conversation_id: null, content: "¿Qué IVA aplico?" };

// --- Origen, cuerpo y sesión ----------------------------------------------------------------------------------------------------------

test("un origen ajeno recibe un 403 y no se mira la sesión ni se llama a la API", async () => {
  for (const headers of [{ "sec-fetch-site": "cross-site" }, { "sec-fetch-site": "same-site" }, { origin: "https://otro.example" }, {}] as Record<string, string>[]) {
    const { deps, calls, counts } = setup(() => stream(["x"]));
    const response = await handleSend(post(OK_BODY, headers), deps);
    assert.equal(response.status, 403);
    assert.equal((await response.json() as { code: string }).code, "forbidden");
    assert.equal(calls.length, 0);
    assert.equal(counts.token, 0);
  }
});

test("el mismo origen se admite por `Sec-Fetch-Site` o, sin él, por `Origin` y `Host`", async () => {
  for (const headers of [{ "sec-fetch-site": "same-origin" }, { origin: "http://localhost:3000" }] as Record<string, string>[]) {
    const { deps } = setup(() => stream(["event: token\ndata: {}\n\n"]));
    assert.equal((await handleSend(post(OK_BODY, headers), deps)).status, 200);
  }
});

test("parseSendBody solo acepta {conversation_id: uuid|null, content: texto}", () => {
  assert.deepEqual(parseSendBody('{"conversation_id":null,"content":"hola"}'), { conversation_id: null, content: "hola" });
  assert.deepEqual(parseSendBody(`{"conversation_id":"${CONVERSATION}","content":""}`), { conversation_id: CONVERSATION, content: "" });
  assert.deepEqual(parseSendBody('{"content":"sin conversación"}'), { conversation_id: null, content: "sin conversación" });
  for (const bad of ["", "no json", "[]", "null", "5", '"x"', "{}", '{"content":5}', '{"content":["a"]}', '{"conversation_id":"no-uuid","content":"a"}', '{"conversation_id":5,"content":"a"}', `{"content":"${"a".repeat(9000)}"}`]) {
    assert.equal(parseSendBody(bad), null, bad.slice(0, 40));
  }
});

test("un cuerpo mal formado o desmesurado es un 422 y no llega a la API", async () => {
  for (const body of ["no json", "[]", { content: 5 }, { conversation_id: "x", content: "a" }, "a".repeat(30_000), JSON.stringify({ content: "a".repeat(30_000) })]) {
    const { deps, calls, counts } = setup(() => stream(["x"]));
    const response = await handleSend(post(body), deps);
    assert.equal(response.status, 422, String(body).slice(0, 30));
    assert.equal(((await response.json()) as { code: string }).code, "invalid_request");
    assert.equal(calls.length, 0);
    assert.equal(counts.token, 0);
  }
});

test("sin sesión es un 401 con `code: session` y la API no se llama", async () => {
  const { deps, calls } = setup(() => stream(["x"]), null);
  const response = await handleSend(post(OK_BODY), deps);
  assert.equal(response.status, 401);
  assert.equal(((await response.json()) as { code: string }).code, "session");
  assert.equal(calls.length, 0);
});

// --- Lo que se reenvía a la API --------------------------------------------------------------------------------------------------------

test("a la API le llega el token de la sesión, el cuerpo tal cual y la señal del navegador", async () => {
  const { deps, calls } = setup(() => stream(["event: token\ndata: {}\n\n"]));
  const request = post({ conversation_id: CONVERSATION, content: "Otra pregunta" });
  await handleSend(request, deps);
  const [call] = calls;
  assert.equal(call?.url, `${BACKEND}/api/chat`);
  assert.equal(call?.init.method, "POST");
  const headers = call?.init.headers as Record<string, string>;
  assert.equal(headers["authorization"], `Bearer ${TOKEN}`);
  assert.equal(headers["content-type"], "application/json");
  assert.equal(headers["accept"], "text/event-stream");
  assert.deepEqual(JSON.parse(String(call?.init.body)), { conversation_id: CONVERSATION, content: "Otra pregunta" });
  assert.equal(call?.init.signal, request.signal); // el corte del navegador llega a la API: guarda lo recibido como «interrumpido»
  assert.equal(call?.init.cache, "no-store");
  assert.equal(call?.init.redirect, "manual");
});

test("el cuerpo reenviado solo lleva los dos campos conocidos: nada más del navegador llega a la API", async () => {
  const { deps, calls } = setup(() => stream(["x"]));
  await handleSend(post({ conversation_id: null, content: "hola", role: "admin", extra: { a: 1 } }), deps);
  assert.deepEqual(JSON.parse(String(calls[0]?.init.body)), { conversation_id: null, content: "hola" });
});

// --- El flujo vuelve sin acumularse -----------------------------------------------------------------------------------------------------

test("el flujo se devuelve tal cual, con las cabeceras que impiden que nadie lo acumule", async () => {
  const text = 'event: start\ndata: {"a":1}\n\nevent: token\ndata: {"delta":"Inversión «x»"}\n\n';
  const { deps } = setup(() => stream([text]));
  const response = await handleSend(post(OK_BODY), deps);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "text/event-stream; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "private, no-store, no-transform");
  assert.equal(response.headers.get("x-accel-buffering"), "no");
  assert.equal(await response.text(), text);
});

test("el primer trozo llega al navegador ANTES de que la API haya terminado de enviar el siguiente", async () => {
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => (release = resolve));
  let secondPulled = false;
  const encoder = new TextEncoder();
  let step = 0;
  const upstream = new Response(
    new ReadableStream<Uint8Array>({
      async pull(controller) {
        if (step === 0) {
          step = 1;
          controller.enqueue(encoder.encode("event: start\ndata: {}\n\n"));
          return;
        }
        await gate; // la API «piensa»: hasta que la prueba lo permita, no sale el segundo trozo
        secondPulled = true;
        controller.enqueue(encoder.encode("event: token\ndata: {}\n\n"));
        controller.close();
      },
    }),
    { status: 200, headers: { "content-type": "text/event-stream; charset=utf-8" } },
  );
  const { deps } = setup(() => upstream);
  const response = await handleSend(post(OK_BODY), deps);
  const reader = response.body?.getReader();
  assert.ok(reader);
  const first = await reader.read(); // si el manejador acumulara el cuerpo, esto no volvería hasta que `gate` se abra: la prueba se colgaría
  assert.equal(new TextDecoder().decode(first.value), "event: start\ndata: {}\n\n");
  assert.equal(secondPulled, false);
  release();
  const second = await reader.read();
  assert.equal(new TextDecoder().decode(second.value), "event: token\ndata: {}\n\n");
  assert.equal((await reader.read()).done, true);
});

test("cancelar la lectura en el navegador cancela el cuerpo de la API (se cierra la conexión)", async () => {
  let cancelled = false;
  const upstream = new Response(
    new ReadableStream<Uint8Array>({ start(c) { c.enqueue(new TextEncoder().encode("event: start\ndata: {}\n\n")); }, cancel() { cancelled = true; } }),
    { status: 200, headers: { "content-type": "text/event-stream" } },
  );
  const { deps } = setup(() => upstream);
  const response = await handleSend(post(OK_BODY), deps);
  const reader = response.body?.getReader();
  await reader?.read();
  await reader?.cancel();
  assert.equal(cancelled, true);
});

test("el JWT de la sesión no vuelve al navegador ni en las cabeceras ni en el cuerpo, y solo un `X-Request-Id` bien formado", async () => {
  const upstream = () => {
    const response = stream(["event: token\ndata: {}\n\n"]);
    return new Response(response.body, { status: 200, headers: { "content-type": "text/event-stream", "x-request-id": "abcd1234efgh5678", "set-cookie": "sb=secreto", authorization: `Bearer ${TOKEN}`, "x-otra": "no" } });
  };
  const { deps } = setup(upstream);
  const response = await handleSend(post(OK_BODY), deps);
  assert.equal(response.headers.get("x-request-id"), "abcd1234efgh5678");
  for (const name of ["set-cookie", "authorization", "x-otra"]) assert.equal(response.headers.get(name), null);
  assert.ok(![...response.headers.values()].some((value) => value.includes(TOKEN)));
  assert.ok(!(await response.text()).includes(TOKEN));

  const odd = setup(() => new Response(stream(["x"]).body, { status: 200, headers: { "content-type": "text/event-stream", "x-request-id": "mal id con espacios <b>" } }));
  assert.equal((await handleSend(post(OK_BODY), odd.deps)).headers.get("x-request-id"), null);
});

// --- Fallos antes del primer frame ---------------------------------------------------------------------------------------------------------

test("los problemas de la API se traducen a {code, message} sin reenviar su cuerpo, con `Retry-After` si lo hay", async () => {
  const cases: { upstream: Response; status: number; code: string; retryAfter: string | null; message?: string }[] = [
    { upstream: problem(429, { code: "chat_rate_limited", detail: "Has enviado muchos mensajes seguidos. Espera un poco y vuelve a intentarlo." }, { "retry-after": "120" }), status: 429, code: "chat_rate_limited", retryAfter: "120", message: "Has enviado muchos mensajes seguidos. Espera un poco y vuelve a intentarlo." },
    { upstream: problem(422, { code: "message_too_long", detail: "El mensaje no puede pasar de 2.000 caracteres." }), status: 422, code: "message_too_long", retryAfter: null, message: "El mensaje no puede pasar de 2.000 caracteres." },
    { upstream: problem(422, { code: "message_empty", detail: "Escribe tu pregunta antes de enviarla." }), status: 422, code: "message_empty", retryAfter: null },
    { upstream: problem(404, { code: "conversation_not_found", detail: "No existe esa conversación." }), status: 404, code: "conversation_not_found", retryAfter: null },
    { upstream: problem(403, { code: "forbidden", detail: "No tienes permiso para acceder a este recurso." }), status: 403, code: "forbidden", retryAfter: null },
    { upstream: problem(401, { code: "unauthenticated", detail: "Tu sesión no es válida." }), status: 401, code: "session", retryAfter: null },
    { upstream: problem(500, { code: "internal_error", detail: "Traza interna SECRETA: /srv/app/x.py línea 3" }), status: 500, code: "internal_error", retryAfter: null },
    { upstream: new Response("<html>502 Bad Gateway SECRETO</html>", { status: 502, headers: { "content-type": "text/html" } }), status: 502, code: "error", retryAfter: null },
  ];
  for (const { upstream, status, code, retryAfter, message } of cases) {
    const { deps } = setup(() => upstream);
    const response = await handleSend(post(OK_BODY), deps);
    assert.equal(response.status, status, code);
    assert.equal(response.headers.get("retry-after"), retryAfter, code);
    assert.equal(response.headers.get("cache-control"), "no-store");
    const body = (await response.json()) as { code: string; message: string };
    assert.equal(body.code, code);
    if (message) assert.equal(body.message, message);
    assert.ok(!JSON.stringify(body).includes("SECRET"), code);
    assert.ok(!JSON.stringify(body).includes("/srv/app"), code);
  }
});

test("un 503 del asistente conserva la conversación en la que quedó guardado el mensaje y el `Retry-After`", async () => {
  const upstream = () => problem(503, { code: "agent_unavailable", detail: "El asistente no está disponible ahora mismo. Tu mensaje se ha guardado: inténtalo de nuevo en unos minutos.", conversation_id: CONVERSATION }, { "retry-after": "5" });
  const { deps } = setup(upstream);
  const response = await handleSend(post(OK_BODY), deps);
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("retry-after"), "5");
  const body = (await response.json()) as { code: string; conversation_id?: string };
  assert.equal(body.code, "agent_unavailable");
  assert.equal(body.conversation_id, CONVERSATION);
});

test("solo un uuid se acepta como `conversation_id` del problema", async () => {
  for (const bad of ["no-uuid", "<script>", 5, null, { a: 1 }]) {
    const { deps } = setup(() => problem(503, { code: "agent_unavailable", detail: "x", conversation_id: bad }));
    const body = (await (await handleSend(post(OK_BODY), deps)).json()) as Record<string, unknown>;
    assert.equal("conversation_id" in body, false, JSON.stringify(bad));
  }
});

test("una respuesta que no es un flujo ni un problema, una redirección o un fallo de red son «servicio no disponible»", async () => {
  const cases: (() => Response | Promise<Response>)[] = [
    () => new Response("{}", { status: 200, headers: { "content-type": "application/json" } }),
    () => new Response(null, { status: 302, headers: { location: "https://otro.example" } }),
    () => new Response(null, { status: 200, headers: { "content-type": "text/event-stream" } }),
    () => {
      throw new Error("ECONNREFUSED 127.0.0.1:8000 SECRETO");
    },
  ];
  for (const upstream of cases) {
    const { deps } = setup(upstream);
    const response = await handleSend(post(OK_BODY), deps);
    assert.equal(response.status, 503);
    const text = await response.text();
    assert.ok(!text.includes("SECRETO") && !text.includes("127.0.0.1") && !text.includes("otro.example"), text);
  }
});

test("un cuerpo de problema desmesurado no se lee entero ni se refleja", async () => {
  const huge = JSON.stringify({ code: "x", detail: "y".repeat(40_000) });
  const { deps } = setup(() => new Response(huge, { status: 400, headers: { "content-type": "application/problem+json" } }));
  const response = await handleSend(post(OK_BODY), deps);
  const body = (await response.json()) as { code: string; message: string };
  assert.equal(response.status, 400);
  assert.ok(body.message.length < 200);
});

// --- Refuerzos (mutaciones que sobrevivían) ----------------------------------------------------------------------------------------------

test("un cuerpo de más de 20 KiB se rechaza aunque sea JSON válido y su mensaje sea corto", async () => {
  const { deps, calls, counts } = setup(() => stream(["x"]));
  const padded = JSON.stringify({ conversation_id: null, content: "hola", relleno: "x".repeat(30_000) });
  const response = await handleSend(post(padded), deps);
  assert.equal(response.status, 422);
  assert.equal(calls.length, 0);
  assert.equal(counts.token, 0);
});

test("solo un 200 con `text/event-stream` es un flujo: un 500 que lo declara es un fallo y se traduce", async () => {
  const upstream = () =>
    new Response(JSON.stringify({ code: "internal_error", detail: "Traza SECRETA" }), { status: 500, headers: { "content-type": "text/event-stream" } });
  const { deps } = setup(upstream);
  const response = await handleSend(post(OK_BODY), deps);
  assert.equal(response.status, 500);
  assert.ok(!(await response.text()).includes("SECRETA"));
});

test("un cuerpo de problema de más de 16 KiB se ignora entero, también lo que tuviera de útil", async () => {
  const body = JSON.stringify({ code: "chat_rate_limited", detail: "Texto útil y corto.", relleno: "y".repeat(40_000) });
  const { deps } = setup(() => new Response(body, { status: 429, headers: { "content-type": "application/problem+json" } }));
  const payload = (await (await handleSend(post(OK_BODY), deps)).json()) as { code: string; message: string };
  assert.equal(payload.code, "error");
  assert.ok(!payload.message.includes("Texto útil"));
});
