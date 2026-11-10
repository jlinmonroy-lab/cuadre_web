// Facturas en la interfaz: formato, filtros de la dirección y la frase de condiciones (SPEC-W-007 §5.5).
import assert from "node:assert/strict";
import { test } from "node:test";

import { conditionsText, formatDate, formatLongDate, kindLabel, madridToday, parseListQuery, paymentLabel, rateText, retentionText, vatText, yearOptions } from "./invoices.ts";

test("las fechas se reordenan sin pasar por Date", () => {
  assert.equal(formatDate("2026-11-09"), "09/11/2026");
  assert.equal(formatDate("2026-01-31T23:30:00+00:00"), "31/01/2026");
  assert.equal(formatDate("no es una fecha"), "no es una fecha");
  assert.equal(formatLongDate("2026-11-09"), "9 de noviembre de 2026");
  assert.equal(formatLongDate("2026-01-31"), "31 de enero de 2026");
  assert.equal(formatLongDate("2026-13-01"), "2026-13-01");
});

test("el día de hoy es el de Madrid, no el de UTC", () => {
  assert.equal(madridToday(new Date("2026-12-31T23:30:00Z")), "2027-01-01");
  assert.equal(madridToday(new Date("2026-07-01T21:59:00Z")), "2026-07-01");
  assert.equal(madridToday(new Date("2026-07-01T22:00:00Z")), "2026-07-02");
});

test("los tipos se enseñan sin ceros sobrantes y con coma", () => {
  assert.equal(rateText("21.00"), "21");
  assert.equal(rateText("7.50"), "7,5");
  assert.equal(rateText("4.00"), "4");
  assert.equal(rateText("0.00"), "0");
  assert.equal(rateText("raro"), "raro");
});

test("el IVA es «Sin IVA» cuando el tipo es 0 y el importe cuando no", () => {
  assert.equal(vatText({ vat_rate: "0.00", vat_cents: 0 }), "Sin IVA");
  assert.match(vatText({ vat_rate: "21.00", vat_cents: 21_000 }), /^210,00\s€$/);
  assert.match(vatText({ vat_rate: "21.00", vat_cents: -4_200 }), /^-42,00\s€$/);
});

test("la retención se ve como lo que se resta: «−» en una ordinaria y «+» si una rectificativa la devuelve", () => {
  assert.equal(retentionText({ irpf_cents: 0 }), "—");
  assert.match(retentionText({ irpf_cents: 15_000 }), /^−150,00\s€$/);
  assert.match(retentionText({ irpf_cents: -3_000 }), /^\+30,00\s€$/);
});

test("el cobro se dice con texto; una rectificativa no se cobra", () => {
  assert.equal(paymentLabel({ kind: "standard", paid_at: null }), "Pendiente");
  assert.equal(paymentLabel({ kind: "standard", paid_at: "2026-11-10T10:00:00Z" }), "Cobrada");
  assert.equal(paymentLabel({ kind: "rectifying", paid_at: null }), null);
  assert.equal(kindLabel("rectifying"), "Rectificativa");
  assert.equal(kindLabel("standard"), "Ordinaria");
});

test("los filtros de la dirección ignoran lo desconocido", () => {
  assert.deepEqual(parseListQuery({}, 2026), { year: 2026, scope: undefined, paid: undefined });
  assert.deepEqual(parseListQuery({ year: "2025", scope: "eu", paid: "unpaid" }, 2026), { year: 2025, scope: "eu", paid: false });
  assert.deepEqual(parseListQuery({ year: "2024", scope: "non_eu", paid: "paid" }, 2026), { year: 2024, scope: "non_eu", paid: true });
  assert.deepEqual(parseListQuery({ year: ["2023", "2020"], scope: ["national"] }, 2026), { year: 2023, scope: "national", paid: undefined });
  // Años fuera de 2000–9998 o mal escritos → el actual
  for (const year of ["1999", "9999", "20", "202x", "2025.5", "-2025", "", " 2025"]) assert.equal(parseListQuery({ year }, 2026).year, 2026, year);
  assert.equal(parseListQuery({ year: "2000" }, 2026).year, 2000);
  assert.equal(parseListQuery({ year: "9998" }, 2026).year, 9998);
  // Ámbito y cobro desconocidos → todos
  assert.equal(parseListQuery({ scope: "mundo" }, 2026).scope, undefined);
  assert.equal(parseListQuery({ scope: "constructor" }, 2026).scope, undefined);
  assert.equal(parseListQuery({ paid: "true" }, 2026).paid, undefined);
});

test("los años que se ofrecen: cinco hacia atrás, más el elegido, el más reciente primero", () => {
  assert.deepEqual(yearOptions(2026, 2026), [2026, 2025, 2024, 2023, 2022]);
  assert.deepEqual(yearOptions(2026, 2019), [2026, 2025, 2024, 2023, 2022, 2019]);
  assert.deepEqual(yearOptions(2026, 2030), [2030, 2026, 2025, 2024, 2023, 2022]);
});

test("las condiciones de cada tratamiento salen de los campos del servidor", () => {
  const cases: [Parameters<typeof conditionsText>[0], string][] = [
    [{ vat_rate: "21.00", irpf_rate: "15.00", legal_note: null }, "Sus facturas llevarán IVA del 21 % y retención de IRPF del 15 %."],
    [{ vat_rate: "21.00", irpf_rate: "7.00", legal_note: null }, "Sus facturas llevarán IVA del 21 % y retención de IRPF del 7 %."],
    [{ vat_rate: "21.00", irpf_rate: "0.00", legal_note: null }, "Sus facturas llevarán IVA del 21 % y sin retención."],
    [
      { vat_rate: "0.00", irpf_rate: "0.00", legal_note: "Inversión del sujeto pasivo" },
      "Sus facturas irán sin IVA y sin retención, con la mención «Inversión del sujeto pasivo».",
    ],
    [
      { vat_rate: "0.00", irpf_rate: "0.00", legal_note: "No sujeta por reglas de localización" },
      "Sus facturas irán sin IVA y sin retención, con la mención «No sujeta por reglas de localización».",
    ],
  ];
  for (const [preview, expected] of cases) assert.equal(conditionsText(preview), expected);
});
