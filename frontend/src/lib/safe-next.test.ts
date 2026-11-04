// `?next=` es la única entrada de usuario que acaba en una redirección: solo se admiten rutas de esta misma aplicación.
import assert from "node:assert/strict";
import { test } from "node:test";

import { safeNext } from "./safe-next.ts";

test("acepta rutas relativas de la propia aplicación", () => {
  for (const ok of ["/inicio", "/cartera", "/admin", "/inicio?mes=2026-10", "/a/b/c", "/inicio#cuota", "/", "/a%20b"]) {
    assert.equal(safeNext(ok), ok);
  }
});

test("sin valor, vacío o con varios valores usa el de reserva", () => {
  for (const nothing of [null, undefined, "", ["/inicio"], ["/a", "/b"], 7, {}, true]) {
    assert.equal(safeNext(nothing as never), "/");
  }
});

test("el valor de reserva es configurable", () => {
  assert.equal(safeNext(null, "/inicio"), "/inicio");
  assert.equal(safeNext("//evil.com", "/cartera"), "/cartera");
});

test("rechaza todo lo que pueda sacar al usuario del sitio", () => {
  const hostile = [
    "//evil.com",
    "///evil.com",
    "//evil.com/inicio",
    "/\\evil.com",
    "\\\\evil.com",
    "\\evil.com",
    "/a\\b",
    "https://evil.com",
    "http://evil.com/x",
    "javascript:alert(1)",
    "data:text/html,x",
    "evil.com",
    "inicio",
    "//",
    "/\t/evil.com",
    "/\n/evil.com",
    "/\r/evil.com",
    "/%2f%2fevil.com",
    "/%2F%2Fevil.com",
    "/%5cevil.com",
    "/%5Cevil.com",
    "/%0a/evil.com",
    "/%09/evil.com",
    " /inicio",
    "/inicio ",
    "/a b",
    "/\u0000",
    "/ini\u0007cio",
    "/\u007f",
    "/\u2028x",
    "/\u0085x",
    "／／evil.com",
  ];
  for (const bad of hostile) {
    assert.equal(safeNext(bad), "/", `debía rechazar ${JSON.stringify(bad)}`);
  }
});

test("una codificación porcentual mal formada no revienta: se rechaza", () => {
  assert.equal(safeNext("/%E0%A4%A"), "/");
  assert.equal(safeNext("/%"), "/");
});

test("el límite de longitud es de 512 caracteres", () => {
  assert.equal(safeNext("/" + "a".repeat(511)), "/" + "a".repeat(511));
  assert.equal(safeNext("/" + "a".repeat(512)), "/");
});
