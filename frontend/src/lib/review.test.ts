// AC-14 · Del formulario de revisión a la API: céntimos enteros, errores POR CAMPO y nada se guarda si algo no se entiende.
import assert from "node:assert/strict";
import { test } from "node:test";

import { AMOUNT_ERROR, MAX_LINES, initialValues, lineCount, lineName, toReviewBody, valuesFromForm, type FormValues } from "./review.ts";

const extraction = {
  doc_type: "full_invoice",
  supplier_name: "Imprenta Sol S.L.",
  supplier_tax_id: null,
  recipient_tax_id: "12345678Z",
  invoice_number: "A-311",
  issue_date: "2026-11-01",
  currency: "EUR",
  tax_breakdown: [{ vat_rate: "21", base_cents: 12000, vat_cents: 2520 }],
  withholding: null,
  total_cents: 14520,
  doubtful_fields: [{ field: "supplier_tax_id", line_index: null, reason: "illegible", raw_text: "B0?0?075" }],
  warnings: [],
} as const;

const blank = (): FormValues => valuesFromForm(() => "");

function filled(changes: FormValues = {}): FormValues {
  return { ...initialValues({ extraction: structuredClone(extraction) as never, review: null }), ...changes };
}

function body(values: FormValues) {
  const result = toReviewBody(values);
  assert.equal(result.ok, true, JSON.stringify(result));
  return result.ok ? result.body : assert.fail();
}

function errors(values: FormValues) {
  const result = toReviewBody(values);
  assert.equal(result.ok, false, "debería haber errores");
  return result.ok ? {} : result.errors;
}

test("los valores iniciales salen de lo leído, con los importes como se escriben en España", () => {
  const values = initialValues({ extraction: structuredClone(extraction) as never, review: null });
  assert.deepEqual(values, {
    doc_type: "full_invoice",
    supplier_name: "Imprenta Sol S.L.",
    supplier_tax_id: "",
    recipient_tax_id: "12345678Z",
    invoice_number: "A-311",
    issue_date: "2026-11-01",
    currency: "EUR",
    total: "145,20",
    withholding_rate: "",
    withholding_amount: "",
    line_count: "1",
    line_0_rate: "21",
    line_0_base: "120,00",
    line_0_vat: "25,20",
  });
});

test("si ya hay correcciones, mandan sobre la lectura", () => {
  const values = initialValues({
    extraction: structuredClone(extraction) as never,
    review: { supplier_tax_id: "B00000075", total_cents: 99, tax_breakdown: [], withholding: { rate: "7.5", amount_cents: 1000 } },
  });
  assert.equal(values["supplier_tax_id"], "B00000075");
  assert.equal(values["total"], "0,99");
  assert.equal(values["supplier_name"], "", "la corrección sustituye a la lectura entera, no se mezclan");
  assert.equal(values["withholding_rate"], "7,5", "coma decimal en el campo");
  assert.equal(values["withholding_amount"], "10,00");
  assert.equal(values["line_count"], "1", "siempre hay al menos una línea para rellenar");
});

test("un documento que no se pudo leer parte de un formulario vacío", () => {
  const values = initialValues({ extraction: null, review: null });
  assert.equal(values["total"], "");
  assert.equal(values["doc_type"], "");
  assert.equal(values["line_count"], "1");
  assert.equal(values["line_0_rate"], undefined);
});

test("las líneas de IVA nunca pasan de diez", () => {
  const many = { ...structuredClone(extraction), tax_breakdown: Array.from({ length: 14 }, () => ({ vat_rate: "21", base_cents: 100, vat_cents: 21 })) };
  const values = initialValues({ extraction: many as never, review: null });
  assert.equal(values["line_count"], String(MAX_LINES));
  assert.equal(values[lineName(MAX_LINES, "base")], undefined);
});

test("valuesFromForm lee solo los campos conocidos y trata lo que no es texto como vacío", () => {
  const raw: Record<string, unknown> = {
    supplier_name: "Acme",
    total: 12, // no es texto
    campo_inventado: "x",
    line_count: "2",
    line_0_base: "10,00",
    line_1_vat: "2,10",
    line_2_base: "se ignora: solo hay 2 líneas",
  };
  const values = valuesFromForm((name) => raw[name]);
  assert.equal(values["supplier_name"], "Acme");
  assert.equal(values["total"], "");
  assert.equal(values["campo_inventado"], undefined);
  assert.equal(values["line_2_base"], undefined);
  assert.equal(values["line_0_base"], "10,00");
  assert.equal(values["line_1_vat"], "2,10");
});

test("valuesFromForm acota el número de líneas", () => {
  for (const [given, expected] of [["", 1], ["0", 1], ["-3", 1], ["abc", 1], ["3", 3], ["10", 10], ["11", 10], ["999999", 10]] as const) {
    assert.equal(lineCount({ line_count: given }), expected, given);
    assert.equal(valuesFromForm((name) => (name === "line_count" ? given : ""))["line_count"], String(expected), given);
  }
});

test("lo leído, sin tocar, se convierte en el cuerpo de la API con céntimos enteros", () => {
  assert.deepEqual(body(filled()), {
    doc_type: "full_invoice",
    supplier_name: "Imprenta Sol S.L.",
    supplier_tax_id: null,
    recipient_tax_id: "12345678Z",
    invoice_number: "A-311",
    issue_date: "2026-11-01",
    currency: "EUR",
    tax_breakdown: [{ vat_rate: "21", base_cents: 12000, vat_cents: 2520 }],
    withholding: null,
    total_cents: 14520,
  });
});

test("AC-14 · se corrige el NIF y un importe y se guarda en céntimos", () => {
  const result = body(filled({ supplier_tax_id: " B00000075 ", total: "1.234,50", line_0_base: "1000", line_0_vat: "210,00" }));
  assert.equal(result.supplier_tax_id, "B00000075");
  assert.equal(result.total_cents, 123450);
  assert.deepEqual(result.tax_breakdown, [{ vat_rate: "21", base_cents: 100000, vat_cents: 21000 }]);
});

test("AC-14 · un importe que no se entiende se señala junto a su campo y no se guarda nada", () => {
  const found = errors(filled({ total: "1.200", line_0_base: "12,345", line_0_vat: "abc", withholding_amount: "1e3" }));
  assert.deepEqual(found, {
    total: AMOUNT_ERROR,
    line_0_base: AMOUNT_ERROR,
    line_0_vat: AMOUNT_ERROR,
    withholding_amount: AMOUNT_ERROR,
  });
  // Un solo error basta para que no haya cuerpo.
  assert.equal(toReviewBody(filled({ total: "doce" })).ok, false);
});

test("los campos vacíos se guardan como null y una línea en blanco no se envía", () => {
  const values = { ...blank(), line_count: "3", line_1_base: "5,00" };
  const result = body(values);
  assert.deepEqual(result.tax_breakdown, [{ vat_rate: null, base_cents: 500, vat_cents: null }]);
  assert.equal(result.total_cents, null);
  assert.equal(result.doc_type, null);
  assert.equal(result.supplier_name, null);
  assert.equal(result.withholding, null);
  assert.equal(result.issue_date, null);
  assert.equal(result.currency, null);
});

test("retención: tipo y/o importe", () => {
  assert.deepEqual(body(filled({ withholding_rate: "15", withholding_amount: "18,00" })).withholding, { rate: "15", amount_cents: 1800 });
  assert.deepEqual(body(filled({ withholding_rate: "7,5" })).withholding, { rate: "7.5", amount_cents: null });
  assert.deepEqual(body(filled({ withholding_amount: "1,00" })).withholding, { rate: null, amount_cents: 100 });
});

test("tipos de IVA: coma o punto, hasta dos decimales", () => {
  assert.equal(body(filled({ line_0_rate: "7,5" })).tax_breakdown?.[0]?.vat_rate, "7.5");
  assert.equal(body(filled({ line_0_rate: " 21 " })).tax_breakdown?.[0]?.vat_rate, "21");
  assert.equal(body(filled({ line_0_rate: "0" })).tax_breakdown?.[0]?.vat_rate, "0");
  for (const bad of ["21%", "1e2", "21,555", "-5", "veintiuno", "1000"]) {
    assert.deepEqual(Object.keys(errors(filled({ line_0_rate: bad }))), ["line_0_rate"], bad);
  }
});

test("fechas: AAAA-MM-DD y de calendario", () => {
  assert.equal(body(filled({ issue_date: "2024-02-29" })).issue_date, "2024-02-29");
  for (const bad of ["2026-02-29", "2026-13-01", "2026-00-10", "01/11/2026", "2026-11-1", "2026-11-01T10:00", "ayer"]) {
    assert.deepEqual(Object.keys(errors(filled({ issue_date: bad }))), ["issue_date"], bad);
  }
});

test("moneda: tres letras, en mayúsculas", () => {
  assert.equal(body(filled({ currency: "usd" })).currency, "USD");
  for (const bad of ["EURO", "E", "12€", "€"]) assert.deepEqual(Object.keys(errors(filled({ currency: bad }))), ["currency"], bad);
});

test("tipo de documento: solo los seis del contrato", () => {
  assert.equal(body(filled({ doc_type: "ticket" })).doc_type, "ticket");
  for (const bad of ["invoice", "constructor", "TICKET"]) assert.deepEqual(Object.keys(errors(filled({ doc_type: bad }))), ["doc_type"], bad);
});

test("longitudes de los textos, contadas en caracteres", () => {
  assert.equal(body(filled({ supplier_name: "ñ".repeat(200) })).supplier_name?.length, 200);
  assert.deepEqual(Object.keys(errors(filled({ supplier_name: "ñ".repeat(201) }))), ["supplier_name"]);
  assert.deepEqual(Object.keys(errors(filled({ supplier_tax_id: "x".repeat(33) }))), ["supplier_tax_id"]);
  assert.deepEqual(Object.keys(errors(filled({ recipient_tax_id: "x".repeat(33) }))), ["recipient_tax_id"]);
  assert.deepEqual(Object.keys(errors(filled({ invoice_number: "x".repeat(65) }))), ["invoice_number"]);
  assert.equal(errors(filled({ supplier_name: "x".repeat(201) }))["supplier_name"], "Máximo 200 caracteres.");
});

test("los textos se limpian: controles fuera, espacios colapsados, HTML tal cual", () => {
  const result = body(filled({ supplier_name: "  Acme\u0000\u202e   S.L.\n<b>x</b>  ", invoice_number: "\u200b\u0007 " }));
  assert.equal(result.supplier_name, "Acme S.L. <b>x</b>");
  assert.equal(result.invoice_number, null);
});

test("no hay más de diez líneas de IVA", () => {
  const values = filled();
  values["line_count"] = "11";
  assert.equal(errors(values)["line_count"], "Como máximo 10 líneas de IVA.");
  values["line_count"] = "10";
  assert.equal(toReviewBody(values).ok, true);
});

test("el cuerpo nunca lleva un número que no sea entero (RES-02)", () => {
  const result = body(filled({ total: "19,99", line_0_base: "0,29", line_0_vat: "1,15", withholding_amount: "4,35", withholding_rate: "15" }));
  const numbers: number[] = [];
  JSON.stringify(result, (_key, value) => {
    if (typeof value === "number") numbers.push(value);
    return value;
  });
  assert.deepEqual(numbers, [29, 115, 435, 1999]); // en el orden del cuerpo: líneas, retención y total
  assert.ok(numbers.every(Number.isInteger));
});
