// Formulario «Gasto sin factura» (AC-11): lo que no se puede interpretar se señala junto a su campo y no se envía.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  AMOUNT_ZERO_ERROR,
  CATEGORY_ERROR,
  CONCEPT_ERROR,
  DATE_ERROR,
  fieldErrorsFromProblem,
  initialExpenseValues,
  toExpenseBody,
  valuesFromExpenseForm,
  type ExpenseFormValues,
} from "./expense-form.ts";
import { AMOUNT_ERROR } from "./review.ts";

const GOOD: ExpenseFormValues = { expense_date: "2026-10-01", concept: "Cuota de autónomos", category: "self_employed_fee", amount: "294,00" };
const body = (changes: Record<string, string>) => toExpenseBody({ ...GOOD, ...changes });
const errors = (changes: Record<string, string>) => {
  const result = body(changes);
  assert.equal(result.ok, false);
  return result.ok ? {} : result.errors;
};

test("un gasto correcto: céntimos enteros, concepto limpio y categoría de la lista", () => {
  assert.deepEqual(body({}), {
    ok: true,
    body: { expense_date: "2026-10-01", concept: "Cuota de autónomos", category: "self_employed_fee", amount_cents: 29400 },
  });
  const spaced = body({ concept: "  Cuota   de\tautónomos \n", amount: "294,00 €" });
  assert.equal(spaced.ok && spaced.body.concept, "Cuota de autónomos");
});

test("importes: la costumbre española, sin float y sin adivinar", () => {
  const cents = (amount: string) => {
    const result = body({ amount });
    return result.ok ? result.body.amount_cents : result.errors["amount"];
  };
  assert.equal(cents("294"), 29400);
  assert.equal(cents("1.234,50"), 123450);
  assert.equal(cents("1234.5"), 123450);
  assert.equal(cents("0,01"), 1);
  assert.equal(cents("0,29"), 29, "trampa de coma flotante");
  assert.equal(cents("4,35"), 435, "trampa de coma flotante");
  assert.equal(cents("999.999.999.999,99"), 99999999999999);
});

test("importes: lo ambiguo, lo vacío y lo no positivo se rechazan junto al campo", () => {
  for (const ambiguous of ["1.200", "12,345", "abc", "1e3", "12,", ",50", "1,2,3", "٣٤٥", "1.000.000.000.000"]) {
    assert.equal(errors({ amount: ambiguous })["amount"], AMOUNT_ERROR, ambiguous);
  }
  assert.equal(errors({ amount: "" })["amount"], "Escribe el importe del gasto.");
  assert.equal(errors({ amount: "   " })["amount"], "Escribe el importe del gasto.");
  for (const zero of ["0", "0,00", "-5", "-0,01"]) assert.equal(errors({ amount: zero })["amount"], AMOUNT_ZERO_ERROR, zero);
});

test("concepto: obligatorio, sin controles y de hasta 200 caracteres (no bytes)", () => {
  for (const empty of ["", "   ", "\u0000\u200b", "\n\t"]) assert.equal(errors({ concept: empty })["concept"], CONCEPT_ERROR, JSON.stringify(empty));
  assert.equal(body({ concept: "ñ".repeat(200) }).ok, true);
  assert.equal(errors({ concept: "ñ".repeat(201) })["concept"], "Máximo 200 caracteres.");
  assert.equal(body({ concept: "😀".repeat(200) }).ok, true, "cuenta caracteres, no unidades UTF-16");
  assert.equal(errors({ concept: "😀".repeat(201) })["concept"], "Máximo 200 caracteres.");
  const withControls = body({ concept: "a\u0000b\u202ec" });
  assert.equal(withControls.ok && withControls.body.concept, "a b c");
});

test("fecha: AAAA-MM-DD y real; el límite de hoy lo decide la API", () => {
  assert.equal(errors({ expense_date: "" })["expense_date"], "Elige la fecha del gasto.");
  for (const bad of ["2026-02-30", "2026-02-29", "2026-13-01", "2026-1-5", "01/02/2026", "ayer", "2026-10-01T10:00:00", "٢٠٢٦-١٠-٠١"]) {
    assert.equal(errors({ expense_date: bad })["expense_date"], DATE_ERROR, bad);
  }
  assert.equal(body({ expense_date: "2024-02-29" }).ok, true, "29 de febrero de un año bisiesto");
  assert.equal(body({ expense_date: "2999-01-01" }).ok, true, "una fecha futura la rechaza la API, con su texto");
});

test("categoría: solo las de la lista", () => {
  for (const bad of ["", "inventada", "Software", "constructor", "__proto__"]) assert.equal(errors({ category: bad })["category"], CATEGORY_ERROR, bad);
  for (const good of ["software", "workspace", "supplies", "utilities", "advisory", "self_employed_fee", "training", "other"]) {
    assert.equal(body({ category: good }).ok, true, good);
  }
});

test("varios fallos a la vez se devuelven todos, cada uno en su campo", () => {
  assert.deepEqual(errors({ concept: "", expense_date: "x", category: "y", amount: "0" }), {
    concept: CONCEPT_ERROR,
    expense_date: DATE_ERROR,
    category: CATEGORY_ERROR,
    amount: AMOUNT_ZERO_ERROR,
  });
});

test("valuesFromExpenseForm lee solo los campos conocidos y solo texto", () => {
  const form = new Map<string, unknown>([
    ["expense_date", "2026-10-01"],
    ["concept", "Cuota"],
    ["category", 5],
    ["amount", undefined],
    ["owner_id", "otra-persona"],
  ]);
  assert.deepEqual(valuesFromExpenseForm((name) => form.get(name)), { expense_date: "2026-10-01", concept: "Cuota", category: "", amount: "" });
});

test("los valores iniciales: hoy, sin concepto y «Cuota de autónomos» como en el prototipo", () => {
  assert.deepEqual(initialExpenseValues("2026-11-07"), { expense_date: "2026-11-07", concept: "", category: "self_employed_fee", amount: "" });
});

// --- Errores de la API por campo ---------------------------------------------------------------------------------------------------

test("invalid_expense: el texto de la API junto al campo que dice, con los nombres del formulario", () => {
  const problem = (field: string) => ({ code: "invalid_expense", message: "Texto de la API.", field });
  assert.deepEqual(fieldErrorsFromProblem(problem("expense_date")), { expense_date: "Texto de la API." });
  assert.deepEqual(fieldErrorsFromProblem(problem("amount_cents")), { amount: "Texto de la API." });
  assert.deepEqual(fieldErrorsFromProblem(problem("concept")), { concept: "Texto de la API." });
  assert.deepEqual(fieldErrorsFromProblem(problem("category")), { category: "Texto de la API." });
  assert.equal(fieldErrorsFromProblem(problem("values")), null);
  assert.equal(fieldErrorsFromProblem({ code: "invalid_expense", message: "x" }), null);
});

test("validation_error: un texto propio en español por campo, nunca el del cuerpo", () => {
  const result = fieldErrorsFromProblem({ code: "validation_error", message: "Revisa los datos enviados.", invalidFields: ["amount_cents", "concept", "owner_id"] });
  assert.deepEqual(result, { amount: AMOUNT_ZERO_ERROR, concept: CONCEPT_ERROR });
  assert.equal(fieldErrorsFromProblem({ code: "validation_error", message: "x", invalidFields: [] }), null);
  assert.equal(fieldErrorsFromProblem({ code: "validation_error", message: "x", invalidFields: ["owner_id"] }), null);
  assert.equal(fieldErrorsFromProblem({ code: "validation_error", message: "x" }), null);
});

test("otros errores no son de un campo", () => {
  for (const code of ["forbidden", "expense_not_found", "internal_error", "error", "validation_failed"]) {
    assert.equal(fieldErrorsFromProblem({ code, message: "x", field: "concept", invalidFields: ["concept"] }), null, code);
  }
});
