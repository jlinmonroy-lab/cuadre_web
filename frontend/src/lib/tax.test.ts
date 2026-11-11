// El borrador del 303 en la interfaz: dirección, trimestres, plazo, resultado y qué casillas se ven (SPEC-W-008 §5.5). Nada de impuestos: solo texto y orden.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  componentsText,
  deadlineBanner,
  groupBoxes,
  itemAmount,
  itemHref,
  itemSummary,
  parseQuarterQuery,
  quarterEnabled,
  quarterHref,
  quarterMonths,
  quarterOfDate,
  quarterTitle,
  resultText,
  visibleBoxes,
  type Box303,
  type Item303,
} from "./tax.ts";

const plain = (text: string) => text.replace(/ /g, " "); // el importe lleva un espacio duro antes del «€»

const invoice = (id: string, label: string, base: number, vat: number): Item303 => ({ kind: "invoice", id, label, date: "2025-02-03", base_cents: base, vat_cents: vat });
const expense = (id: string, label: string, base: number, vat: number): Item303 => ({ kind: "expense", id, label, date: "2025-04-15", base_cents: base, vat_cents: vat });

function box(code: string, group: Box303["group"], measure: Box303["measure"], amount: number, items: Item303[] = [], components: string[] = []): Box303 {
  return { code, label: `Casilla ${code}`, group, measure, amount_cents: amount, items, components };
}

/** Las trece casillas, como las manda el servidor, de un trimestre con solo facturas al 21 % y un gasto. */
function thirteen(opts: { reduced?: boolean } = {}): Box303[] {
  const i21 = [invoice("a", "2025-001", 250, 53)];
  const e = [expense("e", "Papelería", 1000, 210)];
  const r4 = opts.reduced ? [invoice("c", "2025-003", 1237, 49)] : [];
  return [
    box("01", "devengado", "base", opts.reduced ? 1237 : 0, r4),
    box("03", "devengado", "vat", opts.reduced ? 49 : 0, r4),
    box("04", "devengado", "base", 0),
    box("06", "devengado", "vat", 0),
    box("07", "devengado", "base", 250, i21),
    box("09", "devengado", "vat", 53, i21),
    box("27", "devengado", null, 53, [], ["03", "06", "09"]),
    box("28", "deducible", "base", 1000, e),
    box("29", "deducible", "vat", 210, e),
    box("45", "deducible", null, 210, [], ["29"]),
    box("46", "resultado", null, -157, [], ["27", "45"]),
    box("59", "adicional", "base", 0),
    box("120", "adicional", "base", 0),
  ];
}

// --- La dirección ---------------------------------------------------------------------------------------------------------------------

test("el trimestre de una fecha ISO", () => {
  assert.deepEqual(quarterOfDate("2025-01-01"), { year: 2025, quarter: 1 });
  assert.deepEqual(quarterOfDate("2025-03-31"), { year: 2025, quarter: 1 });
  assert.deepEqual(quarterOfDate("2025-04-01"), { year: 2025, quarter: 2 });
  assert.deepEqual(quarterOfDate("2025-09-30"), { year: 2025, quarter: 3 });
  assert.deepEqual(quarterOfDate("2025-10-01"), { year: 2025, quarter: 4 });
  assert.deepEqual(quarterOfDate("2026-12-31"), { year: 2026, quarter: 4 });
});

test("sin parámetros, o con parámetros ilegibles, es el trimestre de hoy", () => {
  const today = "2026-11-11";
  assert.deepEqual(parseQuarterQuery({}, today), { year: 2026, quarter: 4 });
  for (const bad of ["", "abc", "0", "5", "-1", "1.5", "01", " 2", "2e0", "٣"]) {
    assert.deepEqual(parseQuarterQuery({ quarter: bad }, today), { year: 2026, quarter: 4 }, `quarter=${bad}`);
  }
  for (const bad of ["", "abc", "1999", "9999", "20255", "202", "-2025", "2025.0", "٢٠٢٥", "02025", "+2025"]) {
    assert.deepEqual(parseQuarterQuery({ year: bad }, today), { year: 2026, quarter: 4 }, `year=${bad}`);
  }
});

test("lo ausente vale el año y el trimestre de hoy, sea cual sea hoy", () => {
  assert.deepEqual(parseQuarterQuery({}, "2027-02-01"), { year: 2027, quarter: 1 });
  assert.deepEqual(parseQuarterQuery({}, "2025-08-15"), { year: 2025, quarter: 3 });
  assert.deepEqual(parseQuarterQuery({ quarter: "4" }, "2030-01-01"), { year: 2030, quarter: 4 });
  assert.deepEqual(parseQuarterQuery({ year: "2024" }, "2025-08-15"), { year: 2024, quarter: 3 });
});

test("cada parámetro vale por su cuenta y manda el primero si se repite", () => {
  const today = "2026-11-11";
  assert.deepEqual(parseQuarterQuery({ year: "2025" }, today), { year: 2025, quarter: 4 });
  assert.deepEqual(parseQuarterQuery({ quarter: "1" }, today), { year: 2026, quarter: 1 });
  assert.deepEqual(parseQuarterQuery({ year: "2025", quarter: "2" }, today), { year: 2025, quarter: 2 });
  assert.deepEqual(parseQuarterQuery({ year: ["2024", "2025"], quarter: ["3", "1"] }, today), { year: 2024, quarter: 3 });
  assert.deepEqual(parseQuarterQuery({ year: "2000", quarter: "4" }, today), { year: 2000, quarter: 4 });
  assert.deepEqual(parseQuarterQuery({ year: "9998", quarter: "1" }, today), { year: 9998, quarter: 1 });
});

test("un trimestre futuro se deja pasar: lo rechaza el servidor con su texto", () => {
  assert.deepEqual(parseQuarterQuery({ year: "2027", quarter: "1" }, "2026-11-11"), { year: 2027, quarter: 1 });
});

test("títulos, meses y direcciones", () => {
  assert.equal(quarterTitle(2025, 2), "T2 de 2025");
  assert.deepEqual([1, 2, 3, 4].map((q) => quarterMonths(q as 1 | 2 | 3 | 4)), ["enero a marzo", "abril a junio", "julio a septiembre", "octubre a diciembre"]);
  assert.equal(quarterHref(2025, 3), "/trimestres?year=2025&quarter=3");
});

test("un trimestre se ofrece desde su primer día", () => {
  assert.equal(quarterEnabled(2026, 4, "2026-10-01"), true);
  assert.equal(quarterEnabled(2026, 4, "2026-09-30"), false);
  assert.equal(quarterEnabled(2026, 1, "2026-01-01"), true);
  assert.equal(quarterEnabled(2026, 2, "2026-03-31"), false);
  assert.equal(quarterEnabled(2026, 2, "2026-04-01"), true);
  assert.equal(quarterEnabled(2027, 1, "2026-12-31"), false);
  assert.equal(quarterEnabled(2025, 4, "2026-11-11"), true);
  assert.equal(quarterEnabled(2026, 3, "2026-11-11"), true);
});

// --- El plazo y el resultado -----------------------------------------------------------------------------------------------------------

test("el estado del plazo se escribe y lleva la fecha larga del servidor", () => {
  assert.deepEqual(deadlineBanner({ deadline_status: "en_curso", deadline: "2026-01-30" }), {
    label: "Trimestre en curso",
    text: "Se presenta hasta el 30 de enero de 2026.",
    tone: "neutral",
  });
  assert.deepEqual(deadlineBanner({ deadline_status: "plazo_abierto", deadline: "2025-07-20" }), {
    label: "Plazo abierto",
    text: "Presenta hasta el 20 de julio de 2025.",
    tone: "doubt",
  });
  assert.deepEqual(deadlineBanner({ deadline_status: "plazo_cerrado", deadline: "2025-04-20" }), {
    label: "Plazo cerrado",
    text: "El plazo terminó el 20 de abril de 2025.",
    tone: "ok",
  });
});

test("el resultado con palabras: a ingresar, a compensar sin signo, a cero y sin actividad", () => {
  assert.equal(plain(resultText("a_ingresar", 25_598)), "255,98 € a ingresar");
  assert.equal(plain(resultText("a_compensar", -41_110)), "411,10 € a compensar en próximos trimestres");
  assert.equal(resultText("a_cero", 0), "0,00 €: nada que ingresar ni compensar");
  assert.equal(resultText("sin_actividad", 0), "Sin actividad en este trimestre");
  assert.ok(!resultText("a_compensar", -5).includes("-"), "el signo no se repite si el texto ya dice «a compensar»");
});

// --- Qué casillas se ven ----------------------------------------------------------------------------------------------------------------

test("se ocultan 01, 03, 04 y 06 sin documentos y todas las demás salen siempre", () => {
  const codes = (boxes: Box303[]) => visibleBoxes(boxes).map((b) => b.code);
  assert.deepEqual(codes(thirteen()), ["07", "09", "27", "28", "29", "45", "46", "59", "120"]);
  assert.deepEqual(codes(thirteen({ reduced: true })), ["01", "03", "07", "09", "27", "28", "29", "45", "46", "59", "120"]);
  const empty = thirteen().map((b) => ({ ...b, items: [], amount_cents: 0 }));
  assert.deepEqual(codes(empty), ["07", "09", "27", "28", "29", "45", "46", "59", "120"]);
});

test("una casilla oculta solo lo está por no tener documentos, no por valer cero", () => {
  const withItemsButZero = [box("04", "devengado", "base", 0, [invoice("x", "2025-009", 0, 0)])];
  assert.deepEqual(visibleBoxes(withItemsButZero).map((b) => b.code), ["04"]);
});

test("las casillas se agrupan en el orden de la hoja y un grupo vacío no sale", () => {
  const groups = groupBoxes(thirteen());
  assert.deepEqual(groups.map((g) => [g.group, g.label]), [
    ["devengado", "IVA devengado"],
    ["deducible", "IVA deducible"],
    ["resultado", "Resultado"],
    ["adicional", "Información adicional"],
  ]);
  assert.deepEqual(groups[0]?.boxes.map((b) => b.code), ["07", "09", "27"]);
  assert.deepEqual(groups[1]?.boxes.map((b) => b.code), ["28", "29", "45"]);
  assert.deepEqual(groups[3]?.boxes.map((b) => b.code), ["59", "120"]);
  assert.deepEqual(groupBoxes([box("46", "resultado", null, 0, [], ["27", "45"])]).map((g) => g.group), ["resultado"]);
  assert.deepEqual(groupBoxes([]), []);
});

// --- Los documentos de una casilla -------------------------------------------------------------------------------------------------------

test("el resumen del desplegable cuenta y nombra los documentos", () => {
  const inv = (n: number) => ({ items: Array.from({ length: n }, (_, k) => invoice(String(k), `F${k}`, 1, 1)) });
  const exp = (n: number) => ({ items: Array.from({ length: n }, (_, k) => expense(String(k), `P${k}`, 1, 1)) });
  assert.equal(itemSummary(inv(0)), null);
  assert.equal(itemSummary(inv(1)), "Ver la factura");
  assert.equal(itemSummary(inv(3)), "Ver las 3 facturas");
  assert.equal(itemSummary(exp(1)), "Ver el gasto");
  assert.equal(itemSummary(exp(2)), "Ver los 2 gastos");
});

test("una factura lleva a su detalle y un gasto, a la lista de gastos", () => {
  assert.equal(itemHref({ kind: "invoice", id: "3f2a" }), "/facturas/3f2a");
  assert.equal(itemHref({ kind: "expense", id: "3f2a" }), "/gastos");
});

test("el importe de un documento es la base o la cuota según lo que suma la casilla, con su signo", () => {
  const item = invoice("r", "R-2025-001", -20_000, -4_200);
  assert.equal(plain(itemAmount(item, "base")), "-200,00 €");
  assert.equal(plain(itemAmount(item, "vat")), "-42,00 €");
  assert.equal(plain(itemAmount(invoice("a", "2025-001", 250, 53), "base")), "2,50 €");
  assert.equal(plain(itemAmount(invoice("a", "2025-001", 250, 53), null)), "2,50 €");
});

test("las casillas derivadas dicen de cuáles se componen", () => {
  assert.equal(componentsText({ code: "27", components: ["03", "06", "09"] }), "Suma de las casillas 03, 06 y 09");
  assert.equal(componentsText({ code: "45", components: ["29"] }), "Igual a la casilla 29");
  assert.equal(componentsText({ code: "46", components: ["27", "45"] }), "Casilla 27 menos casilla 45");
  assert.equal(componentsText({ code: "99", components: ["03", "06"] }), "Suma de las casillas 03 y 06");
  assert.equal(componentsText({ code: "07", components: [] }), null);
});
