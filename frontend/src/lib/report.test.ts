// El reporte mensual en la interfaz: porcentajes con enteros, geometría y textos. La interfaz no calcula ningún importe.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  MONTH_OPTIONS,
  SET_ASIDE_NOTE,
  barPercent,
  categoriesSummary,
  clientsSummary,
  NO_PREVIOUS_MONTH,
  columnPercents,
  deltaText,
  formatBp,
  quarterLinks,
  reportHref,
  scopesSummary,
  shortMonth,
  trendStatus,
  trendSummary,
  variationText,
  type MonthlyReport,
} from "./report.ts";

const NBSP = " ";
const euros = (text: string): string => text.replace(/ €/g, `${NBSP}€`);

test("formatBp: puntos básicos a porcentaje con décimas y solo con enteros", () => {
  assert.equal(formatBp(0), "0,0 %");
  assert.equal(formatBp(1), "0,0 %");
  assert.equal(formatBp(4), "0,0 %");
  assert.equal(formatBp(5), "0,1 %"); // medio: sube (half-up)
  assert.equal(formatBp(50), "0,5 %");
  assert.equal(formatBp(95), "1,0 %"); // arrastre a la unidad siguiente
  assert.equal(formatBp(99), "1,0 %");
  assert.equal(formatBp(100), "1,0 %");
  assert.equal(formatBp(2_000), "20,0 %");
  assert.equal(formatBp(8_333), "83,3 %");
  assert.equal(formatBp(26_050), "260,5 %");
  assert.equal(formatBp(-8_333), "83,3 %"); // el signo lo pone `variationText`
  assert.equal(formatBp(10_000), "100,0 %");
});

test("variationText: con signo y con palabras, y sin referencia cuando el servidor no la da", () => {
  assert.equal(variationText(2_000, 8), "+20,0 % frente a agosto");
  assert.equal(variationText(-6_500, 10), "−65,0 % frente a octubre");
  assert.equal(variationText(0, 12), "sin cambios frente a diciembre");
  assert.equal(variationText(null, 8), "sin referencia del mes anterior");
  assert.equal(variationText(3, 1), "+0,0 % frente a enero"); // una variación de 0,03 % existe y no es «sin cambios»
});

test("deltaText: la diferencia del servidor con su signo y sin recalcular", () => {
  assert.equal(deltaText(26_050, 8), euros("+260,50 € frente a agosto"));
  assert.equal(deltaText(-6_050, 8), euros("-60,50 € frente a agosto"));
  assert.equal(deltaText(0, 8), "sin cambios frente a agosto");
  assert.match(NO_PREVIOUS_MONTH, /mes anterior/);
});

test("barPercent: entero de 0 a 100, mínimo 1 si hay algo y 0 si no hay nada que dibujar", () => {
  assert.equal(barPercent(100, 100), 100);
  assert.equal(barPercent(50, 100), 50);
  assert.equal(barPercent(1, 1_000_000), 1); // una barra pequeña se ve
  assert.equal(barPercent(0, 100), 0);
  assert.equal(barPercent(-5_000, 100), 0); // una rectificativa no dibuja barra
  assert.equal(barPercent(100, 0), 0);
  assert.equal(barPercent(100, -3), 0);
  assert.equal(barPercent(150, 100), 100); // nunca pasa de 100
  assert.equal(barPercent(1.5, 100), 0); // los importes son enteros: lo demás no se dibuja
  assert.equal(barPercent(Number.NaN, 100), 0);
  assert.equal(barPercent(1, 3), 33);
  assert.equal(barPercent(2, 3), 67);
});

test("columnPercents: una escala común a ingresos y gastos", () => {
  const columns = columnPercents([
    { total_cents: 100_000, expenses_cents: 10_000 },
    { total_cents: 50_000, expenses_cents: 200_000 },
    { total_cents: 0, expenses_cents: 0 },
  ]);
  assert.deepEqual(columns, [
    { income: 50, expenses: 5 },
    { income: 25, expenses: 100 },
    { income: 0, expenses: 0 },
  ]);
  assert.deepEqual(columnPercents([]), []);
  assert.deepEqual(columnPercents([{ total_cents: 0, expenses_cents: 0 }]), [{ income: 0, expenses: 0 }]);
});

test("reportHref, shortMonth y los doce meses del selector", () => {
  assert.equal(reportHref(2026, 9), "/reporte?anio=2026&mes=9");
  assert.equal(shortMonth(1), "ene.");
  assert.equal(shortMonth(9), "sept.");
  assert.equal(shortMonth(12), "dic.");
  assert.equal(shortMonth(13), "");
  assert.equal(MONTH_OPTIONS.length, 12);
  assert.deepEqual(MONTH_OPTIONS[0], { value: 1, label: "Enero" });
  assert.deepEqual(MONTH_OPTIONS[11], { value: 12, label: "Diciembre" });
});

test("quarterLinks: el 303 y el 130 del trimestre del mes, sin importes", () => {
  assert.deepEqual(quarterLinks(2026, 3), { modelo303: "/trimestres?year=2026&quarter=3", modelo130: "/trimestres?model=130&year=2026&quarter=3" });
  assert.ok(!/\d\s?€|\d+,\d\d/.test(SET_ASIDE_NOTE), "la nota de apartar no lleva ningún importe");
  assert.match(SET_ASIDE_NOTE, /Orientativo/);
});

const REPORT = {
  year: 2026,
  month: 9,
  by_client: [
    { client_id: "c1", name: "Estudio Norte S.L.", scope: "national", base_cents: 90_000, invoice_count: 1 },
    { client_id: "c2", name: "Kreativ GmbH", scope: "eu", base_cents: 30_000, invoice_count: 1 },
  ],
  scopes: [
    { scope: "national", base_cents: 90_000, share_bp: 7_500 },
    { scope: "eu", base_cents: 30_000, share_bp: 2_500 },
    { scope: "non_eu", base_cents: 0, share_bp: 0 },
  ],
  expenses_by_category: [{ category: "advisory", label: "Asesoría", expenses_cents: 30_000, expense_count: 1 }],
  trend: [
    { year: 2026, month: 8, status: "closed", total_cents: 100_000, expenses_cents: 10_000, result_cents: 90_000 },
    { year: 2026, month: 9, status: "in_progress", total_cents: 120_000, expenses_cents: 36_050, result_cents: 83_950 },
  ],
} as unknown as MonthlyReport;

test("los resúmenes de los gráficos dicen las cifras del servidor, tal cual", () => {
  assert.equal(clientsSummary(REPORT), euros("Ingresos por cliente en septiembre de 2026: Estudio Norte S.L. (Nacional), 900,00 €; Kreativ GmbH (UE), 300,00 €."));
  assert.equal(scopesSummary(REPORT), euros("Ingresos por ámbito en septiembre de 2026: Nacional, 900,00 €, 75,0 %; UE, 300,00 €, 25,0 %; Fuera de la UE, 0,00 €, 0,0 %."));
  assert.equal(categoriesSummary(REPORT), euros("Gastos por categoría en septiembre de 2026: Asesoría, 300,00 €."));
  assert.equal(
    trendSummary(REPORT),
    euros("Ingresos y gastos de los últimos meses: Agosto de 2026, ingresos 1000,00 €, gastos 100,00 €; Septiembre de 2026, ingresos 1200,00 €, gastos 360,50 €."),
  );
  assert.equal(trendStatus(REPORT.trend[1]!), "en curso");
});

test("los resúmenes sin datos lo dicen en lugar de quedar vacíos", () => {
  const empty = { ...REPORT, by_client: [], expenses_by_category: [], trend: [], scopes: [] } as unknown as MonthlyReport;
  assert.equal(clientsSummary(empty), "Ingresos por cliente en septiembre de 2026: no hay facturas emitidas.");
  assert.equal(categoriesSummary(empty), "Gastos por categoría en septiembre de 2026: no hay gastos.");
  assert.equal(trendSummary(empty), "Ingresos y gastos de los últimos meses: sin datos.");
  assert.equal(scopesSummary(empty), "Ingresos por ámbito en septiembre de 2026: sin datos.");
});

test("una cuota nula no se escribe como 0 %", () => {
  const negative = { ...REPORT, scopes: [{ scope: "national", base_cents: -40_000, share_bp: null }] } as unknown as MonthlyReport;
  assert.equal(scopesSummary(negative), euros("Ingresos por ámbito en septiembre de 2026: Nacional, -400,00 €."));
});

test("el módulo no usa decimales de coma flotante para importes (RES-02)", () => {
  const source = readFileSync(new URL("./report.ts", import.meta.url), "utf8");
  assert.ok(!/parseFloat|toFixed|Number\(/.test(source));
});
