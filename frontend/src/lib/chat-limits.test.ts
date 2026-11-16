// Los topes del lector del flujo, justo en el límite y uno más (SPEC-W-004 D-10, AC-18), y los casos finos del formato.
import assert from "node:assert/strict";
import { test } from "node:test";

import { ChatEventParser, ChatStreamError, MAX_EVENT_CHARS, MAX_LINE_CHARS, MAX_REPLY_CHARS, readChatStream } from "./chat.ts";

const tooLong = (e: unknown, reason: string) => e instanceof ChatStreamError && e.reason === reason;

test("una línea de exactamente el tope pasa y un carácter más lanza un error", () => {
  const exact = `data: ${"a".repeat(MAX_LINE_CHARS - "data: ".length)}`;
  assert.equal(exact.length, MAX_LINE_CHARS);
  assert.doesNotThrow(() => new ChatEventParser().feed(`event: ping\n${exact}\n\n`));
  assert.throws(() => new ChatEventParser().feed(`event: ping\n${exact}a\n\n`), (e) => tooLong(e, "line_too_long"));
});

test("una línea que no acaba nunca: pasa hasta el tope y lanza un error con un carácter más (sin esperar al salto de línea)", () => {
  const parser = new ChatEventParser();
  assert.doesNotThrow(() => parser.feed("a".repeat(MAX_LINE_CHARS)));
  assert.equal(parser.pending, true);
  assert.throws(() => parser.feed("a"), (e) => tooLong(e, "line_too_long"));
  const waiting = new ChatEventParser();
  assert.doesNotThrow(() => waiting.feed("a".repeat(MAX_LINE_CHARS - 1) + "\r")); // el `\r` espera a un posible `\n`
});

test("un evento de exactamente el tope pasa y un carácter más lanza un error", () => {
  const half = "b".repeat(MAX_EVENT_CHARS / 2 - "data: ".length);
  assert.doesNotThrow(() => new ChatEventParser().feed(`data: ${half}\ndata: ${half}\n\n`)); // las dos líneas suman justo el tope
  const full = "b".repeat(MAX_EVENT_CHARS / 2 - "data: ".length);
  assert.throws(() => new ChatEventParser().feed(`data: ${full}\ndata: ${full}\ndata: x\n\n`), (e) => tooLong(e, "event_too_long"));
  assert.doesNotThrow(() => new ChatEventParser().feed(`data: ${full}\ndata: ${full}\n\n`));
  const shorter = "b".repeat(MAX_EVENT_CHARS / 2 - "data: ".length - 1);
  assert.doesNotThrow(() => new ChatEventParser().feed(`data: ${full}\ndata: ${shorter}\nd\n\n`)); // 32.768 + 32.767 + 1 = el tope
  assert.throws(() => new ChatEventParser().feed(`data: ${full}\ndata: ${shorter}\ndd\n\n`), (e) => tooLong(e, "event_too_long")); // un carácter más
});

test("el tope del evento vuelve a empezar con cada evento", () => {
  const line = `data: ${"c".repeat(MAX_EVENT_CHARS / 2 - "data: ".length)}\n`;
  assert.doesNotThrow(() => new ChatEventParser().feed(`${line}${line}\n${line}${line}\n${line}${line}\n`));
});

test("un solo espacio tras los dos puntos se quita en el nombre del evento: con dos, el nombre es otro y se descarta", () => {
  const parser = new ChatEventParser();
  assert.deepEqual(parser.feed('event:  token\ndata: {"delta":"a"}\n\n'), []);
  assert.deepEqual(parser.feed('event:token\ndata: {"delta":"a"}\n\n').map((e) => e.event), ["token"]);
  assert.deepEqual(parser.feed('event: token\ndata: {"delta":"b"}\n\n').map((e) => e.event), ["token"]);
});

test("un evento con nombre y sin datos no es un evento (ni siquiera uno conocido) y su nombre no se pega al siguiente", () => {
  const parser = new ChatEventParser();
  assert.deepEqual(parser.feed('event: token\n\nevent: token\ndata: {"delta":"a"}\n\n'), [{ event: "token", data: { delta: "a" } }]);
  assert.deepEqual(parser.feed('event: done\n\ndata: {"delta":"b"}\n\n'), []); // `data` sin nombre es «message»: desconocido
  assert.equal(parser.ended, false);
});

test("una línea sin dos puntos es un campo sin valor y se ignora", () => {
  assert.deepEqual(new ChatEventParser().feed('event\ndata: {"delta":"a"}\n\nevent: token\ndata: {"delta":"b"}\n\n').map((e) => e.event), ["token"]);
});

function comments(bytes: number): ReadableStream<Uint8Array> {
  const line = `: ${"x".repeat(997)}\n`; // 1.000 bytes
  const all = line.repeat(Math.floor(bytes / 1000)) + "\n".repeat(bytes % 1000); // las líneas en blanco sobrantes no dicen nada
  const data = new TextEncoder().encode(all);
  let offset = 0;
  return new ReadableStream({
    pull(controller) {
      if (offset >= data.length) return controller.close();
      controller.enqueue(data.slice(offset, offset + 50_000));
      offset += 50_000;
    },
  });
}

test("el flujo entero tiene un tope: justo el tope pasa (y se cierra sin terminal) y un byte más lanza un error", async () => {
  const limit = MAX_REPLY_CHARS * 64;
  assert.equal(await readChatStream(comments(limit), () => undefined), "closed");
  await assert.rejects(readChatStream(comments(limit + 1), () => undefined), (e) => tooLong(e, "stream_too_long"));
});
