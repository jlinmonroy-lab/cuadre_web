// Formulario de recordatorios ↔ API: la casilla ausente es «no», la antelación es texto → entero y el rango NO lo decide la interfaz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { describeProblem } from "./problems.ts";
import {
  LEAD_DAYS_ERROR,
  fieldErrorsFromRemindersProblem,
  toRemindersBody,
  valuesFromRemindersForm,
  valuesFromSettings,
} from "./reminders-form.ts";

test("lo guardado se pinta como texto y casilla", () => {
  assert.deepEqual(valuesFromSettings({ enabled: false, lead_days: 14 }), { enabled: false, lead_days: "14" });
});

test("una casilla sin marcar no viaja: ausente es false, y solo `on` es true", () => {
  const data: Record<string, unknown> = { lead_days: "7", otro: "x" };
  assert.deepEqual(valuesFromRemindersForm((name) => data[name]), { enabled: false, lead_days: "7" });
  assert.equal(valuesFromRemindersForm((name) => ({ enabled: "on", lead_days: "7" })[name as "enabled"]).enabled, true);
  assert.equal(valuesFromRemindersForm((name) => ({ enabled: "true" })[name as "enabled"]).enabled, false);
  assert.equal(valuesFromRemindersForm(() => 5).lead_days, "");
});

test("un entero viaja como número y los espacios se ignoran", () => {
  assert.deepEqual(toRemindersBody({ enabled: true, lead_days: " 14 " }), { ok: true, body: { enabled: true, lead_days: 14 } });
});

test("el rango NO lo decide la interfaz: 0 y 31 viajan y los rechaza el servidor", () => {
  assert.deepEqual(toRemindersBody({ enabled: true, lead_days: "0" }), { ok: true, body: { enabled: true, lead_days: 0 } });
  assert.deepEqual(toRemindersBody({ enabled: true, lead_days: "31" }), { ok: true, body: { enabled: true, lead_days: 31 } });
});

test("lo que no es un entero no se envía y se señala junto al campo", () => {
  for (const text of ["", "  ", "abc", "7.5", "7,5", "1e2", "+7", "1 0", "9999999"]) {
    assert.deepEqual(toRemindersBody({ enabled: true, lead_days: text }), { ok: false, errors: { lead_days: LEAD_DAYS_ERROR } }, text);
  }
});

test("invalid_lead_days se señala en el campo con el texto del servidor", () => {
  const problem = describeProblem({
    status: 422,
    body: { code: "invalid_lead_days", detail: "La antelación debe ser un número entero de días entre 1 y 30.", field: "lead_days" },
    retryAfter: null,
  });
  assert.deepEqual(fieldErrorsFromRemindersProblem(problem), { lead_days: problem.message });
});

test("otros problemas no son de campo", () => {
  const problem = describeProblem({ status: 503, body: {}, retryAfter: null });
  assert.equal(fieldErrorsFromRemindersProblem(problem), null);
});
