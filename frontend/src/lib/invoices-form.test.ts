// Formularios de factura y rectificativa ↔ cuerpo de la API (SPEC-W-007 §5.5): importes en céntimos, vacío = null y errores por campo.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  fieldErrorsFromInvoiceProblem,
  invoiceFailure,
  isInvoiceId,
  toInvoiceBody,
  toPreviewRequest,
  toRectificationBody,
  valuesFromInvoiceForm,
  valuesFromRectifyForm,
} from "./invoices-form.ts";
import type { Problem } from "./problems.ts";

const ID = "3f2a1b4c-5d6e-4f70-8192-a3b4c5d6e7f8";

test("solo se leen los campos conocidos y lo que no es texto cuenta como vacío", () => {
  const form: Record<string, unknown> = {
    client_id: ID,
    series_id: "",
    concept: "Diseño",
    base: "1.200,00",
    total_cents: "5",
    kind: "rectifying",
    issue_date: null,
    vat_rate: new Blob(["x"]),
  };
  const values = valuesFromInvoiceForm((name) => form[name]);
  assert.deepEqual(Object.keys(values), ["client_id", "series_id", "issue_date", "concept", "base", "vat_rate"]);
  assert.equal(values["client_id"], ID);
  assert.equal(values["issue_date"], "");
  assert.equal(values["vat_rate"], "");
  assert.deepEqual(Object.keys(valuesFromRectifyForm(() => "x")), ["reason", "corrected_base", "annul", "issue_date"]);
});

test("el cuerpo de emitir: vacío = null y el importe tecleado en euros pasa a céntimos enteros", () => {
  assert.deepEqual(toInvoiceBody({ client_id: ID, series_id: "", issue_date: "2026-11-10", concept: "  Diseño  ", base: "1.200,00", vat_rate: "10" }), {
    client_id: ID,
    series_id: null,
    issue_date: "2026-11-10",
    concept: "Diseño",
    base_cents: 120_000,
    vat_rate: "10",
  });
  assert.equal(toInvoiceBody({ base: "1234,5" }).base_cents, 123_450);
  assert.equal(toInvoiceBody({ base: "0,07" }).base_cents, 7);
  assert.equal(toInvoiceBody({ base: "12 €" }).base_cents, 1_200);
  // Ambiguo, ilegible o vacío → null: que el servidor diga qué importe espera
  for (const base of ["1.200", "mil", "1e3", "", "  ", "12,345"]) assert.equal(toInvoiceBody({ base }).base_cents, null, base);
  // Controles fuera
  assert.equal(toInvoiceBody({ concept: "a\u0000b‮b" }).concept, "a b b");
  assert.equal(toInvoiceBody({}).client_id, null);
});

test("la vista previa rellena con valores neutros lo que aún falta y dice si el importe vale", () => {
  const filled = toPreviewRequest({ client_id: ID, base: "1.200,00", concept: "Diseño", issue_date: "2026-11-01" }, "2026-11-10");
  assert.equal(filled.base, "ok");
  assert.deepEqual(filled.body, { client_id: ID, series_id: null, issue_date: "2026-11-01", concept: "Diseño", base_cents: 120_000, vat_rate: null });

  const empty = toPreviewRequest({ client_id: ID, base: "" }, "2026-11-10");
  assert.equal(empty.base, "empty");
  assert.deepEqual(empty.body, { client_id: ID, series_id: null, issue_date: "2026-11-10", concept: "Vista previa", base_cents: 100_000, vat_rate: null });

  for (const base of ["1.200", "abc", "0,00", "-5"]) {
    const request = toPreviewRequest({ client_id: ID, base }, "2026-11-10");
    assert.equal(request.base, "invalid", base);
    assert.equal(request.body.base_cents, 100_000, base);
  }
});

test("el cuerpo de rectificar: «anular» fija la base corregida en 0 escriba lo que escriba", () => {
  assert.deepEqual(toRectificationBody({ reason: "  Error  ", corrected_base: "800,00", issue_date: "2026-11-10" }), {
    reason: "Error",
    corrected_base_cents: 80_000,
    issue_date: "2026-11-10",
  });
  assert.equal(toRectificationBody({ reason: "x", corrected_base: "800,00", annul: "on" }).corrected_base_cents, 0);
  assert.equal(toRectificationBody({ reason: "x", corrected_base: "800,00", annul: "" }).corrected_base_cents, 80_000);
  assert.equal(toRectificationBody({ reason: "x", corrected_base: "0,00" }).corrected_base_cents, 0);
  assert.equal(toRectificationBody({ reason: "x", corrected_base: "" }).corrected_base_cents, null);
  assert.equal(toRectificationBody({ reason: "", issue_date: "" }).reason, null);
});

const problem = (overrides: Partial<Problem>): Problem => ({
  status: 422,
  code: "invalid_invoice",
  message: "Revisa los campos marcados: no se ha emitido nada.",
  ...overrides,
});

test("invalid_invoice: todos los campos a la vez y el importe se enseña en «base»", () => {
  const p = problem({
    invoiceFields: [
      { field: "client_id", message: "Elige un cliente." },
      { field: "base_cents", message: "Escribe un importe mayor que cero, por ejemplo 1.200,00." },
      { field: "corrected_base_cents", message: "Escribe la base corregida." },
      { field: "reason", message: "Escribe el motivo." },
      { field: "base_cents", message: "segundo, se ignora" },
    ],
  });
  assert.deepEqual(fieldErrorsFromInvoiceProblem(p, "invoice"), {
    client_id: "Elige un cliente.",
    base: "Escribe un importe mayor que cero, por ejemplo 1.200,00.",
  });
  assert.deepEqual(fieldErrorsFromInvoiceProblem(p, "rectification"), { corrected_base: "Escribe la base corregida.", reason: "Escribe el motivo." });
  assert.equal(fieldErrorsFromInvoiceProblem(problem({ code: "invoice_changed", status: 409 }), "invoice"), null);
  assert.equal(fieldErrorsFromInvoiceProblem(problem({ invoiceFields: [{ field: "reason", message: "x" }] }), "invoice"), null);
});

test("cliente no facturable, serie agotada y fecha fuera de orden se señalan junto a su campo", () => {
  const billable = problem({ status: 409, code: "client_not_billable", message: "Falta el domicilio del cliente.", field: "address" });
  assert.deepEqual(fieldErrorsFromInvoiceProblem(billable, "invoice"), { client_id: "Falta el domicilio del cliente." });
  assert.deepEqual(fieldErrorsFromInvoiceProblem({ ...billable, field: "client_id" }, "invoice"), { client_id: "Falta el domicilio del cliente." });
  const exhausted = problem({ status: 409, code: "series_exhausted", message: "Serie agotada.", field: "series_id" });
  assert.deepEqual(fieldErrorsFromInvoiceProblem(exhausted, "invoice"), { series_id: "Serie agotada." });
  const order = problem({ status: 409, code: "invoice_date_out_of_order", message: "Fecha antigua.", field: "issue_date" });
  assert.deepEqual(fieldErrorsFromInvoiceProblem(order, "invoice"), { issue_date: "Fecha antigua." });
  assert.deepEqual(fieldErrorsFromInvoiceProblem(order, "rectification"), { issue_date: "Fecha antigua." });
  // Sin campo no hay error de campo
  const withoutField = problem({ status: 409, code: "invoice_date_out_of_order", message: "Fecha antigua." });
  assert.equal(fieldErrorsFromInvoiceProblem(withoutField, "invoice"), null);
});

test("el estado tras un error: el titular solo si dice más que los campos", () => {
  const values = { concept: "Diseño" };
  const many = invoiceFailure(problem({ invoiceFields: [{ field: "client_id", message: "Elige un cliente." }] }), values, "invoice");
  assert.deepEqual(many, {
    status: "error",
    values,
    code: "invalid_invoice",
    message: "Revisa los campos marcados: no se ha emitido nada.",
    fieldErrors: { client_id: "Elige un cliente." },
  });

  const single = invoiceFailure(problem({ status: 409, code: "series_exhausted", message: "Serie agotada.", field: "series_id" }), values, "invoice");
  assert.deepEqual(single, { status: "error", values, code: "series_exhausted", fieldErrors: { series_id: "Serie agotada." } });

  const general = invoiceFailure(problem({ status: 409, code: "rectification_exceeds", message: "No puede subir el importe." }), values, "rectification");
  assert.deepEqual(general, { status: "error", values, code: "rectification_exceeds", message: "No puede subir el importe." });

  const missing = [{ field: "tax_id", label: "NIF" }];
  const incomplete = invoiceFailure(problem({ code: "profile_incomplete", message: "Completa tu perfil.", missing }), values, "invoice");
  assert.deepEqual(incomplete, { status: "error", values, code: "profile_incomplete", message: "Completa tu perfil.", missing });
});

test("los ids de factura son UUID", () => {
  assert.equal(isInvoiceId(ID), true);
  for (const bad of ["", "1", ID.toUpperCase(), `${ID}x`, `../${ID}`, undefined, null, 5]) assert.equal(isInvoiceId(bad), false, String(bad));
});
