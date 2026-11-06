// Errores de la API traducidos para la persona: se enseña el `detail` de un 4xx corto y limpio y nunca el cuerpo de un 5xx.
import assert from "node:assert/strict";
import { test } from "node:test";

import { SERVICE_UNAVAILABLE, describeProblem } from "./problems.ts";

test("un 4xx con detalle enseña el detalle en español y conserva el código", () => {
  assert.deepEqual(
    describeProblem({ status: 413, body: { code: "file_too_large", detail: "El archivo supera el máximo de 15 MB." } }),
    { status: 413, code: "file_too_large", message: "El archivo supera el máximo de 15 MB." },
  );
});

test("Retry-After en segundos enteros y acotado", () => {
  const body = { code: "too_many_processing", detail: "Ya hay 5 documentos leyéndose." };
  assert.equal(describeProblem({ status: 429, body, retryAfter: "10" }).retryAfter, 10);
  for (const bad of ["0", "-3", "abc", "1.5", "", "301", "Wed, 21 Oct 2026 07:28:00 GMT", null, undefined]) {
    assert.equal(describeProblem({ status: 429, body, retryAfter: bad }).retryAfter, undefined, String(bad));
  }
});

test("un 5xx nunca enseña su cuerpo", () => {
  const problem = describeProblem({ status: 500, body: { code: "internal_error", detail: "Traceback (most recent call last): secret" } });
  assert.equal(problem.code, "internal_error");
  assert.equal(problem.message, "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.");
  assert.ok(!problem.message.includes("Traceback"));
  assert.equal(describeProblem({ status: 502, body: "<html>Bad Gateway</html>" }).message, SERVICE_UNAVAILABLE.message);
});

test("un detalle sospechoso (largo, con marcas o con controles) no se enseña", () => {
  const fallback = describeProblem({ status: 404, body: {} }).message;
  assert.equal(fallback, "No encontramos ese documento.");
  for (const detail of ["x".repeat(301), "<script>alert(1)</script>", "con\u0007control", "", 5, null, {}]) {
    assert.equal(describeProblem({ status: 404, body: { code: "x", detail } }).message, fallback, JSON.stringify(detail));
  }
});

test("mensajes por estado cuando no hay detalle", () => {
  assert.match(describeProblem({ status: 401, body: null }).message, /sesión ha caducado/);
  assert.match(describeProblem({ status: 403, body: null }).message, /no tiene permiso/);
  assert.match(describeProblem({ status: 404, body: null }).message, /No encontramos ese documento/);
  assert.match(describeProblem({ status: 418, body: null }).message, /No hemos podido completar la operación/);
});

test("el código solo puede ser un identificador estable", () => {
  for (const code of ["Mal Código", "<b>", "x".repeat(80), "", 3, null, "1abc", "../x"]) {
    assert.equal(describeProblem({ status: 400, body: { code, detail: "ok" } }).code, "error", JSON.stringify(code));
  }
  assert.equal(describeProblem({ status: 400, body: { code: "validation_error", detail: "ok" } }).code, "validation_error");
});

test("cuerpos que no son un objeto no rompen nada", () => {
  for (const body of [null, undefined, "texto", 42, [1, 2], true]) {
    const problem = describeProblem({ status: 500, body });
    assert.equal(problem.code, "error");
  }
});
