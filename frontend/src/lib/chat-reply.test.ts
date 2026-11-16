// Casos finos del estado de la respuesta en curso (SPEC-W-004 §5.5): el tope del texto, la herramienta que se apaga, el identificador del mensaje y lo que
// es una respuesta que nunca terminó.
import assert from "node:assert/strict";
import { test } from "node:test";

import { MAX_REPLY_CHARS, applyEvent, fromReply, interrupted, startReply, type ChatEvent } from "./chat.ts";

const START = "66666666-7777-4888-8999-aaaaaaaaaaaa";
const OTHER = "99999999-8888-4777-8666-bbbbbbbbbbbb";
const CONVERSATION = "0b0d0a2e-7a66-4c6f-9b0e-1d3a5c7e9f11";
const USER = "11111111-2222-4333-8444-555555555555";

const start: ChatEvent = { event: "start", data: { conversation_id: CONVERSATION, user_message_id: USER, message_id: START } };
const token = (delta: string): ChatEvent => ({ event: "token", data: { delta } });

test("el texto nunca pasa de 8.000 caracteres aunque un trozo cruce el tope: se corta en el límite y lo que sigue se ignora", () => {
  let reply = startReply();
  for (const size of [3000, 3000, 3000, 500]) reply = applyEvent(reply, token("a".repeat(size)));
  assert.equal(reply.text.length, MAX_REPLY_CHARS);
  assert.equal(reply.text, "a".repeat(MAX_REPLY_CHARS));
  assert.equal(applyEvent(reply, token("más")).text.length, MAX_REPLY_CHARS);
});

test("una herramienta consultándose se apaga en cuanto termina o falla, antes del terminal", () => {
  let reply = applyEvent(startReply(), start);
  reply = applyEvent(reply, { event: "tool_call", data: { name: "buscar_facturas", status: "started" } });
  assert.equal(reply.tool, "buscar_facturas");
  assert.equal(applyEvent(reply, { event: "tool_call", data: { name: "buscar_facturas", status: "finished" } }).tool, null);
  assert.equal(applyEvent(reply, { event: "tool_call", data: { name: "buscar_facturas", status: "failed" } }).tool, null);
});

test("el identificador del mensaje es el del último evento que lo trae: el `error` manda sobre el `start`, y sin el suyo se queda el del `start`", () => {
  const started = applyEvent(startReply(), start);
  assert.equal(started.messageId, START);
  const withOwn = applyEvent(started, { event: "error", data: { code: "timeout", message: "Fijo.", message_id: OTHER } });
  assert.equal(withOwn.messageId, OTHER);
  const without = applyEvent(started, { event: "error", data: { code: "timeout", message: "Fijo.", message_id: null } });
  assert.equal(without.messageId, START);
});

test("una respuesta que no ha terminado no se da por completa: sin terminal es interrumpida y no se puede valorar", () => {
  const live = applyEvent(startReply(), token("a medias"));
  assert.equal(live.status, "streaming");
  const message = fromReply(live, "local-1");
  assert.equal(message.status, "interrupted");
  assert.equal(message.saved, false);
  assert.equal(message.id, "local-1");
  assert.equal(fromReply(interrupted(live), "local-2").status, "interrupted");
});

test("una respuesta terminada con error tiene su texto fijo y se puede valorar (el servidor la guardó)", () => {
  const reply = [start, token("parte"), { event: "error", data: { code: "agent_error", message: "Texto fijo.", message_id: OTHER } } as ChatEvent].reduce(applyEvent, startReply());
  const message = fromReply(reply, "local");
  assert.equal(message.status, "error");
  assert.equal(message.errorMessage, "Texto fijo.");
  assert.equal(message.saved, true);
  assert.equal(message.id, OTHER);
  assert.equal(message.content, "parte");
});
