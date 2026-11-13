// La contabilidad mensual en la interfaz: dirección, mes por defecto y textos. La interfaz no calcula ningún importe.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  COVERAGE_NOTE,
  chooseMonth,
  closingNote,
  monthHref,
  monthName,
  monthTitle,
  parseMonthlyQuery,
  statusLabel,
  type MonthRow,
} from "./monthly.ts";

const TODAY = "2026-11-13";

function row(month: number, status: MonthRow["status"], revision: number | null = status === "closed" ? 1 : null): MonthRow {
  return {
    month,
    status,
    invoice_count: 0,
    national_cents: 0,
    eu_cents: 0,
    non_eu_cents: 0,
    total_cents: 0,
    expenses_cents: 0,
    result_cents: 0,
    ytd_cents: 0,
    revision,
    closed_at: null,
  };
}

test("los nombres de los meses", () => {
  assert.equal(monthName(1), "enero");
  assert.equal(monthName(12), "diciembre");
  assert.equal(monthName(0), "");
  assert.equal(monthName(13), "");
  assert.equal(monthTitle(9), "Septiembre");
  assert.equal(monthTitle(13), "");
});

test("la dirección: cada parámetro por su cuenta y lo ilegible vale el de hoy o ninguno", () => {
  assert.deepEqual(parseMonthlyQuery({}, TODAY), { year: 2026, month: null });
  assert.deepEqual(parseMonthlyQuery({ anio: "2025", mes: "9" }, TODAY), { year: 2025, month: 9 });
  assert.deepEqual(parseMonthlyQuery({ anio: ["2024", "2023"], mes: ["12", "1"] }, TODAY), { year: 2024, month: 12 });
  assert.deepEqual(parseMonthlyQuery({ anio: "abcd", mes: "x" }, TODAY), { year: 2026, month: null });
  assert.deepEqual(parseMonthlyQuery({ anio: "1999", mes: "13" }, TODAY), { year: 2026, month: null });
  assert.deepEqual(parseMonthlyQuery({ anio: "10000", mes: "0" }, TODAY), { year: 2026, month: null });
  assert.deepEqual(parseMonthlyQuery({ anio: "2027", mes: "09" }, TODAY), { year: 2027, month: null }); // un año futuro se pasa tal cual: lo rechaza el servidor
});

test("el mes que se enseña: el pedido, si no el último cerrado y, si no hay, el último", () => {
  const rows = [row(8, "closed"), row(9, "closed"), row(10, "pending"), row(11, "in_progress")];
  assert.equal(chooseMonth(rows, 10)?.month, 10);
  assert.equal(chooseMonth(rows, null)?.month, 9);
  assert.equal(chooseMonth(rows, 3)?.month, 9); // un mes que no está en la lista no rompe nada
  assert.equal(chooseMonth([row(11, "in_progress")], null)?.month, 11);
  assert.equal(chooseMonth([], 5), null);
});

test("las direcciones y las etiquetas de estado", () => {
  assert.equal(monthHref(2026, 9), "/mensual?anio=2026&mes=9");
  assert.equal(statusLabel("closed"), "Cerrado");
  assert.equal(statusLabel("in_progress"), "En curso");
  assert.equal(statusLabel("pending"), "Pendiente de cierre");
});

test("la nota de cierre dice cuándo se cierra y qué pasa con un documento atrasado", () => {
  assert.match(closingNote(row(9, "closed"), 2026), /^Cerrado automáticamente el 1 de octubre\. Si llega una factura o un gasto atrasado, el mes se reabre y se vuelve a cerrar\.$/);
  assert.match(closingNote(row(12, "closed"), 2026), /1 de enero de 2027/);
  assert.equal(closingNote(row(11, "in_progress"), 2026), "Este mes se cerrará automáticamente el 1 de diciembre.");
  assert.equal(closingNote(row(12, "in_progress"), 2026), "Este mes se cerrará automáticamente el 1 de enero de 2027.");
  assert.match(closingNote(row(10, "pending"), 2026), /próxima ejecución diaria/);
});

test("un mes reabierto lo dice con su revisión", () => {
  assert.match(closingNote(row(9, "closed", 2), 2026), /Se ha vuelto a cerrar 1 vez \(revisión 2\)\.$/);
  assert.match(closingNote(row(9, "closed", 4), 2026), /Se ha vuelto a cerrar 3 veces \(revisión 4\)\.$/);
  assert.doesNotMatch(closingNote(row(9, "closed", 1), 2026), /revisión/);
});

test("el aviso de cobertura habla de 12 meses y de bases sin IVA", () => {
  assert.match(COVERAGE_NOTE, /12 meses/);
  assert.match(COVERAGE_NOTE, /sin IVA/);
});
