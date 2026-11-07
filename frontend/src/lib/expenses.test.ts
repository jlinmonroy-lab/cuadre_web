// Gastos en la interfaz: etiquetas completas contra el contrato, la regla de «Registrar gasto», las marcas, el cursor y las fechas.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  CATEGORY_LABELS,
  CHECK_CODES,
  DEFAULT_MANUAL_CATEGORY,
  EXPENSE_CATEGORIES,
  categoryLabel,
  checkView,
  cursorParam,
  expenseBadges,
  formatDay,
  isCheckCode,
  isExpenseCategory,
  isExpenseId,
  madridDay,
  registerGate,
  type Validation,
} from "./expenses.ts";

const OPENAPI = JSON.parse(readFileSync(new URL("../../../backend/openapi.json", import.meta.url), "utf8")) as {
  components: { schemas: Record<string, { enum?: string[] }> };
};

// --- Categorías y códigos: el contrato manda ------------------------------------------------------------------------------------

test("las ocho categorías y sus etiquetas son las del prototipo, en el orden del contrato", () => {
  assert.deepEqual(EXPENSE_CATEGORIES, OPENAPI.components.schemas["ExpenseCategory"]?.enum);
  assert.deepEqual(
    EXPENSE_CATEGORIES.map((category) => CATEGORY_LABELS[category]),
    ["Software", "Coworking y oficina", "Material", "Suministros y teléfono", "Asesoría", "Cuota de autónomos", "Formación", "Otros"],
  );
  assert.equal(new Set(Object.values(CATEGORY_LABELS)).size, 8, "no hay dos etiquetas iguales");
});

test("los códigos de comprobación son los del contrato", () => {
  assert.deepEqual([...CHECK_CODES].sort(), [...(OPENAPI.components.schemas["CheckCode"]?.enum ?? [])].sort());
  assert.equal(CHECK_CODES.length, 11);
});

test("isExpenseCategory y isCheckCode solo aceptan valores de la lista, ni siquiera nombres de Object.prototype", () => {
  for (const category of EXPENSE_CATEGORIES) assert.equal(isExpenseCategory(category), true, category);
  for (const code of CHECK_CODES) assert.equal(isCheckCode(code), true, code);
  for (const bad of ["", "Software", "inventada", "constructor", "__proto__", "toString", "hasOwnProperty", null, undefined, 3, ["other"], {}]) {
    assert.equal(isExpenseCategory(bad), false, String(bad));
    assert.equal(isCheckCode(bad), false, String(bad));
  }
});

test("categoryLabel y la categoría por omisión", () => {
  assert.equal(categoryLabel("advisory"), "Asesoría");
  assert.equal(categoryLabel("constructor"), "Sin categoría");
  assert.equal(categoryLabel(null), "Sin categoría");
  assert.equal(categoryLabel(undefined), "Sin categoría");
  assert.equal(DEFAULT_MANUAL_CATEGORY, "self_employed_fee");
});

test("un identificador de gasto es un UUID", () => {
  assert.equal(isExpenseId("2f1c1f0e-3b8e-4a7e-9a52-0c2f6a2d3b11"), true);
  for (const bad of ["", "no-es-un-uuid", "../x", "2f1c1f0e3b8e4a7e9a520c2f6a2d3b11", null, 5]) assert.equal(isExpenseId(bad), false, String(bad));
});

// --- «Registrar gasto» ---------------------------------------------------------------------------------------------------------------

const validation = (overrides: Partial<Validation> = {}): Validation => ({
  can_register: true,
  requires_acknowledgement: false,
  checks: [],
  warnings: [],
  preview: { supplier_scope: "national", deductible_vat: true, deductible_note: null, suggested_category: "software" },
  ...overrides,
});

test("registerGate: solo se puede con todo guardado, en verde y, si hace falta, reconocido", () => {
  const ok = { dirty: false, acknowledged: false, pending: false };
  assert.deepEqual(registerGate({ ...ok, validation: validation() }), { enabled: true, reason: null });
  assert.deepEqual(registerGate({ ...ok, validation: validation({ requires_acknowledgement: true }), acknowledged: true }), { enabled: true, reason: null });
  // Marcar la casilla sin necesidad no estorba.
  assert.equal(registerGate({ ...ok, validation: validation(), acknowledged: true }).enabled, true);
});

test("registerGate: cada motivo para no poder, con su texto", () => {
  const base = { dirty: false, acknowledged: false, pending: false, validation: validation() };
  assert.deepEqual(registerGate({ ...base, dirty: true }), { enabled: false, reason: "Guarda los cambios para volver a comprobar." });
  assert.deepEqual(registerGate({ ...base, validation: null }), { enabled: false, reason: "Rellena y guarda los datos de la factura para poder comprobarlos." });
  assert.deepEqual(registerGate({ ...base, validation: validation({ can_register: false }) }), {
    enabled: false,
    reason: "Corrige las comprobaciones marcadas y guarda los cambios.",
  });
  assert.deepEqual(registerGate({ ...base, validation: validation({ requires_acknowledgement: true }) }), {
    enabled: false,
    reason: "Marca que has comparado los datos con el original.",
  });
  assert.deepEqual(registerGate({ ...base, pending: true }), { enabled: false, reason: null });
});

test("registerGate: la prioridad de los motivos (registrando > sin guardar > sin datos > fallos > casilla)", () => {
  const failing = validation({ can_register: false, requires_acknowledgement: true });
  assert.equal(registerGate({ validation: failing, dirty: true, acknowledged: false, pending: true }).reason, null);
  assert.equal(registerGate({ validation: failing, dirty: true, acknowledged: false, pending: false }).reason, "Guarda los cambios para volver a comprobar.");
  assert.equal(registerGate({ validation: null, dirty: true, acknowledged: false, pending: false }).reason, "Guarda los cambios para volver a comprobar.");
  assert.equal(registerGate({ validation: failing, dirty: false, acknowledged: false, pending: false }).reason, "Corrige las comprobaciones marcadas y guarda los cambios.");
});

test("registerGate: la casilla nunca arregla una comprobación que falla (NFR-07)", () => {
  const failing = validation({ can_register: false, requires_acknowledgement: true });
  assert.equal(registerGate({ validation: failing, dirty: false, acknowledged: true, pending: false }).enabled, false);
});

test("checkView: texto además de color, con el motivo de las que fallan", () => {
  assert.deepEqual(checkView({ code: "total", label: "Base más IVA igual al total", status: "ok", detail: null }), {
    ok: true,
    label: "Base más IVA igual al total",
    detail: null,
    statusText: "Correcta",
  });
  assert.deepEqual(checkView({ code: "total", label: "Base más IVA igual al total", status: "failed", detail: "Base más IVA da 145,20 € y el total indicado es 147,00 €." }), {
    ok: false,
    label: "Base más IVA igual al total",
    detail: "Base más IVA da 145,20 € y el total indicado es 147,00 €.",
    statusText: "Por revisar",
  });
  assert.equal(checkView({ code: "currency", label: "Importe en euros", status: "failed", detail: null }).detail, "Revisa este dato.");
});

// --- Marcas ---------------------------------------------------------------------------------------------------------------------

const badge = (overrides: Partial<Parameters<typeof expenseBadges>[0]>) =>
  expenseBadges({ origin: "document", vat_cents: 521, deductible_vat: true, supplier_scope: "national", ...overrides }).map((b) => b.label);

test("marcas: «Sin factura», «UE» e «IVA no deducible», solo cuando corresponden y en ese orden", () => {
  assert.deepEqual(badge({}), []);
  assert.deepEqual(badge({ origin: "manual", vat_cents: 0, deductible_vat: false, supplier_scope: null }), ["Sin factura"]);
  assert.deepEqual(badge({ deductible_vat: false }), ["IVA no deducible"]);
  assert.deepEqual(badge({ supplier_scope: "eu", deductible_vat: false }), ["UE", "IVA no deducible"]);
  assert.deepEqual(badge({ supplier_scope: "eu", deductible_vat: false, vat_cents: 0 }), ["UE"], "sin IVA no hay nada que deducir");
  assert.deepEqual(badge({ vat_cents: 0, deductible_vat: false }), []);
});

test("las marcas llevan un tono para el color, que nunca va solo", () => {
  const tones = expenseBadges({ origin: "document", vat_cents: 100, deductible_vat: false, supplier_scope: "eu" });
  assert.deepEqual(tones, [
    { label: "UE", tone: "eu" },
    { label: "IVA no deducible", tone: "doubt" },
  ]);
});

// --- Cursor ---------------------------------------------------------------------------------------------------------------------

test("cursorParam solo acepta la forma de un cursor", () => {
  assert.equal(cursorParam("eyJkIjoiMjAyNi0wMS0wMSJ9"), "eyJkIjoiMjAyNi0wMS0wMSJ9");
  assert.equal(cursorParam("a_b-c"), "a_b-c");
  assert.equal(cursorParam("a".repeat(200)), "a".repeat(200));
  for (const bad of ["", "a".repeat(201), "a b", "../etc", "a=b", "a/b", "<script>", "ñ", undefined, null, 3, ["abc"], {}]) {
    assert.equal(cursorParam(bad), null, String(bad));
  }
});

// --- Fechas ---------------------------------------------------------------------------------------------------------------------

test("formatDay: es-ES, sin pasar por la zona horaria del navegador y sin arreglar fechas imposibles", () => {
  assert.equal(formatDay("2026-10-28"), "28/10/2026");
  assert.equal(formatDay("2024-02-29"), "29/02/2024");
  assert.equal(formatDay("2000-01-01"), "01/01/2000");
  for (const bad of ["2026-02-30", "2026-02-29", "2026-13-01", "2026-1-5", "01/02/2026", "", "ayer", null, undefined]) {
    assert.equal(formatDay(bad as never), "—", String(bad));
  }
});

test("madridDay: el día de Madrid, no el de UTC", () => {
  assert.equal(madridDay(new Date("2026-12-31T23:30:00Z")), "2027-01-01", "en invierno Madrid va una hora por delante");
  assert.equal(madridDay(new Date("2026-06-30T22:30:00Z")), "2026-07-01", "en verano, dos");
  assert.equal(madridDay(new Date("2026-10-27T22:30:00Z")), "2026-10-27");
  assert.equal(madridDay(new Date("2026-10-27T23:30:00Z")), "2026-10-28");
});
