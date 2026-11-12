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

// --- SPEC-W-003: campos de un gasto ---------------------------------------------------------------------------------------------------

test("invalid_expense: el campo viene de una lista cerrada", () => {
  const body = (field: unknown) => ({ code: "invalid_expense", detail: "La fecha no puede ser futura.", field });
  assert.equal(describeProblem({ status: 422, body: body("expense_date") }).field, "expense_date");
  for (const bad of ["owner_id", "values", "", "constructor", "__proto__", 3, null, ["concept"]]) {
    assert.equal("field" in describeProblem({ status: 422, body: body(bad) }), false, String(bad));
  }
});

test("validation_failed: solo códigos de comprobación conocidos y sin repetir", () => {
  const problem = describeProblem({
    status: 422,
    body: { code: "validation_failed", detail: "Corrige los datos.", failed_checks: ["total", "total", "supplier_tax_id", "hackeado", 3, "constructor", null] },
  });
  assert.deepEqual(problem.failedChecks, ["total", "supplier_tax_id"]);
  assert.equal("failedChecks" in describeProblem({ status: 422, body: { code: "validation_failed", failed_checks: [] } }), false);
  assert.equal("failedChecks" in describeProblem({ status: 422, body: { code: "validation_failed", failed_checks: "total" } }), false);
});

test("validation_error: los campos salen de las ubicaciones del cuerpo y de una lista cerrada", () => {
  const problem = describeProblem({
    status: 422,
    body: {
      code: "validation_error",
      detail: "Revisa los datos enviados.",
      errors: [{ loc: "body.concept", msg: "x" }, { loc: "body.amount_cents", msg: "x" }, { loc: "body.concept", msg: "y" }, { loc: "body.owner_id", msg: "z" }, { loc: "query.month", msg: "z" }, "texto", null, { msg: "sin loc" }],
    },
  });
  assert.deepEqual(problem.invalidFields, ["concept", "amount_cents"]);
  // Solo con ese código: el mismo cuerpo bajo otro no cuenta.
  assert.equal("invalidFields" in describeProblem({ status: 422, body: { code: "otra", errors: [{ loc: "body.concept" }] } }), false);
});

test("un 5xx no devuelve ninguno de los campos del cuerpo", () => {
  const problem = describeProblem({
    status: 500,
    body: { code: "validation_error", field: "concept", failed_checks: ["total"], errors: [{ loc: "body.concept" }] },
  });
  assert.deepEqual(problem, { status: 500, code: "validation_error", message: "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos." });
});

test("invalid_profile devuelve todos los campos con su texto, de una lista cerrada y sin reflejar texto libre", () => {
  const body = {
    code: "invalid_profile",
    detail: "Revisa los campos marcados: no se ha guardado nada.",
    fields: [
      { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
      { field: "iban", message: "El IBAN no es válido: revisa los dígitos de control." },
      { field: "logo_path", message: "no es un campo del perfil" },
      { field: "home_pct", message: "con <marca>" },
      { field: "activity", message: "x".repeat(301) },
      { field: "legal_name", message: 5 },
      "texto",
    ],
  };
  assert.deepEqual(describeProblem({ status: 422, body }).profileFields, [
    { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
    { field: "iban", message: "El IBAN no es válido: revisa los dígitos de control." },
  ]);
  assert.equal(describeProblem({ status: 500, body }).profileFields, undefined);
  assert.equal(describeProblem({ status: 422, body: { ...body, code: "otra_cosa" } }).profileFields, undefined);
});

test("invalid_client devuelve todos los campos con su texto, de una lista cerrada y sin reflejar texto libre", () => {
  const body = {
    code: "invalid_client",
    detail: "Revisa los campos marcados: no se ha guardado nada.",
    fields: [
      { field: "name", message: "Escribe el nombre del cliente." },
      { field: "country", message: "Elige un país de la lista." },
      { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
      { field: "owner_id", message: "no es un campo del cliente" },
      { field: "iban", message: "tampoco es de la ficha de cliente" },
      { field: "address", message: "con <marca>" },
      { field: "kind", message: "x".repeat(301) },
      { field: "name", message: 5 },
      "texto",
    ],
  };
  assert.deepEqual(describeProblem({ status: 422, body }).clientFields, [
    { field: "name", message: "Escribe el nombre del cliente." },
    { field: "country", message: "Elige un país de la lista." },
    { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
  ]);
  assert.equal(describeProblem({ status: 500, body }).clientFields, undefined);
  assert.equal(describeProblem({ status: 422, body: { ...body, code: "invalid_profile" } }).clientFields, undefined);
  // Cada problema usa SU lista: un `invalid_client` no rellena los campos del perfil, y un `invalid_profile` solo se queda con los suyos
  // (`tax_id` e `iban` lo son; `name`, `country`, `kind` y `address` no).
  assert.equal(describeProblem({ status: 422, body }).profileFields, undefined);
  assert.deepEqual(describeProblem({ status: 422, body: { ...body, code: "invalid_profile" } }).profileFields, [
    { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
    { field: "iban", message: "tampoco es de la ficha de cliente" },
  ]);
});

test("invalid_series señala su campo de una lista cerrada", () => {
  for (const field of ["code", "description", "first_number"]) {
    assert.equal(describeProblem({ status: 422, body: { code: "invalid_series", detail: "Mal.", field } }).field, field);
  }
  assert.equal(describeProblem({ status: 422, body: { code: "invalid_series", detail: "Mal.", field: "owner_id" } }).field, undefined);
});

test("invalid_invoice devuelve todos los campos de la factura con su texto, de una lista cerrada", () => {
  const body = {
    code: "invalid_invoice",
    detail: "Revisa los campos marcados: no se ha emitido nada.",
    fields: [
      { field: "client_id", message: "Elige un cliente." },
      { field: "issue_date", message: "La fecha no puede ser futura." },
      { field: "base_cents", message: "Escribe un importe mayor que cero, por ejemplo 1.200,00." },
      { field: "corrected_base_cents", message: "Escribe la base corregida (0 si se anula la factura)." },
      { field: "owner_id", message: "no es un campo de la factura" },
      { field: "concept", message: "con <marca>" },
      { field: "reason", message: "x".repeat(301) },
      { field: "vat_rate", message: 5 },
      "texto",
    ],
  };
  assert.deepEqual(describeProblem({ status: 422, body }).invoiceFields, [
    { field: "client_id", message: "Elige un cliente." },
    { field: "issue_date", message: "La fecha no puede ser futura." },
    { field: "base_cents", message: "Escribe un importe mayor que cero, por ejemplo 1.200,00." },
    { field: "corrected_base_cents", message: "Escribe la base corregida (0 si se anula la factura)." },
  ]);
  assert.equal(describeProblem({ status: 500, body }).invoiceFields, undefined);
  assert.equal(describeProblem({ status: 422, body: { ...body, code: "invalid_client" } }).invoiceFields, undefined);
  // Un `invalid_invoice` no rellena los campos de la ficha de cliente.
  assert.equal(describeProblem({ status: 422, body }).clientFields, undefined);
});

test("profile_incomplete lista lo que falta en el perfil, solo con campos del perfil y etiquetas seguras", () => {
  const body = {
    code: "profile_incomplete",
    detail: "Completa tu perfil para poder emitir facturas.",
    missing: [
      { field: "tax_id", label: "NIF" },
      { field: "fiscal_address", label: "Domicilio fiscal" },
      { field: "owner_id", label: "ajeno" },
      { field: "legal_name", label: "con <marca>" },
      { field: "iban", label: "" },
      { field: "activity", label: "x".repeat(301) },
      { field: "home_pct", label: 3 },
      "texto",
    ],
  };
  assert.deepEqual(describeProblem({ status: 422, body }).missing, [
    { field: "tax_id", label: "NIF" },
    { field: "fiscal_address", label: "Domicilio fiscal" },
  ]);
  assert.equal(describeProblem({ status: 500, body }).missing, undefined);
  assert.equal(describeProblem({ status: 422, body: { ...body, code: "otra_cosa" } }).missing, undefined);
});

test("los errores de cliente no facturable, serie agotada y fecha fuera de orden señalan su campo", () => {
  for (const [code, field] of [
    ["client_not_billable", "client_id"],
    ["client_not_billable", "address"],
    ["series_exhausted", "series_id"],
    ["invoice_date_out_of_order", "issue_date"],
  ] as const) {
    assert.equal(describeProblem({ status: 409, body: { code, detail: "Mal.", field } }).field, field);
  }
  assert.equal(describeProblem({ status: 409, body: { code: "client_not_billable", detail: "Mal.", field: "owner_id" } }).field, undefined);
});

test("invalid_note: solo los campos `body` y `entity` de la lista cerrada, y solo con ese código", () => {
  const body = {
    code: "invalid_note",
    detail: "Lo que enlazas no existe o no es de este autónomo.",
    fields: [
      { field: "entity", message: "No válido." },
      { field: "owner_id", message: "No válido." },
      { field: "body", message: "<b>x</b>" },
      { field: "body", message: "No válido." },
    ],
  };
  assert.deepEqual(describeProblem({ status: 422, body }).noteFields, [
    { field: "entity", message: "No válido." },
    { field: "body", message: "No válido." },
  ]);
  assert.equal(describeProblem({ status: 500, body }).noteFields, undefined);
  assert.equal(describeProblem({ status: 422, body: { ...body, code: "invalid_client" } }).noteFields, undefined);
  assert.equal(describeProblem({ status: 422, body: { code: "invalid_note", detail: "x" } }).noteFields, undefined);
});
