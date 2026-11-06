// Defensa CSRF de los Route Handlers de lectura (SPEC-W-002 §5.5, ver `same-origin.ts`).
import assert from "node:assert/strict";
import { test } from "node:test";

import { isSameOrigin, originHeaders } from "./same-origin.ts";

const check = (secFetchSite: string | null, origin: string | null, host: string | null) => isSameOrigin({ secFetchSite, origin, host });

test("Sec-Fetch-Site manda: solo «same-origin» pasa", () => {
  assert.equal(check("same-origin", null, null), true);
  for (const other of ["same-site", "cross-site", "none", "Same-Origin", "same-origin "]) assert.equal(check(other, "http://localhost:3000", "localhost:3000"), false, other);
});

test("con Sec-Fetch-Site presente, el Origin no puede arreglar nada", () => {
  assert.equal(check("cross-site", "http://localhost:3000", "localhost:3000"), false);
});

test("sin Sec-Fetch-Site, el Origin tiene que ser el Host", () => {
  assert.equal(check(null, "http://localhost:3000", "localhost:3000"), true);
  assert.equal(check("", "https://app.cuadre.es", "app.cuadre.es"), true);
  assert.equal(check(null, "https://evil.test", "app.cuadre.es"), false);
  assert.equal(check(null, "http://localhost:3000.evil.test", "localhost:3000"), false);
  assert.equal(check(null, "http://localhost:3001", "localhost:3000"), false);
  assert.equal(check(null, "https://sub.app.cuadre.es", "app.cuadre.es"), false);
});

test("sin ninguna cabecera, o con basura, se rechaza", () => {
  assert.equal(check(null, null, "localhost:3000"), false);
  assert.equal(check(null, "http://localhost:3000", null), false);
  assert.equal(check(null, null, null), false);
  assert.equal(check(null, "no es una url", "localhost:3000"), false);
  assert.equal(check(null, "null", "localhost:3000"), false); // Origin: null (iframe con sandbox, redirecciones entre sitios)
});

test("originHeaders prefiere X-Forwarded-Host al Host", () => {
  const headers = new Headers({ origin: "https://app.cuadre.es", host: "interno:3000", "x-forwarded-host": "app.cuadre.es", "sec-fetch-site": "same-origin" });
  assert.deepEqual(originHeaders(headers), { secFetchSite: "same-origin", origin: "https://app.cuadre.es", host: "app.cuadre.es" });
  assert.deepEqual(originHeaders(new Headers({ host: "localhost:3000" })), { secFetchSite: null, origin: null, host: "localhost:3000" });
});

test("un Origin que solo EMPIEZA igual que el Host no es el mismo origen", () => {
  assert.equal(check(null, "https://app.cuadre.es.evil.test", "app.cuadre.es"), false);
  assert.equal(check(null, "http://localhost.evil.test", "localhost"), false);
  assert.equal(check(null, "https://app.cuadre.es", "app.cuadre.es"), true);
});
