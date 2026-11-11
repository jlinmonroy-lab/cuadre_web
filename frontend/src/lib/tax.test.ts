// Los borradores del 303 y del 130 en la interfaz: dirección, trimestres, plazo, resultado y qué casillas se ven (SPEC-W-008 y SPEC-W-009, §5.5). Nada de impuestos: solo texto y orden.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  boxView130,
  boxView303,
  componentsText,
  componentsText130,
  deadlineBanner,
  groupBoxes,
  groupBoxes130,
  itemAmount,
  itemHref,
  itemHref130,
  itemSummary,
  itemSummary130,
  parseModel,
  parseQuarterQuery,
  quarterEnabled,
  quarterHref,
  quarterMonths,
  quarterOfDate,
  quarterTitle,
  resultText,
  resultText130,
  visibleBoxes,
  withheldShareText,
  type Box130,
  type Box303,
  type Item130,
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

// --- Modelo 130 (SPEC-W-009 §5.5) -----------------------------------------------------------------------------------------------------------

const inv130 = (id: string, label: string, cents: number): Item130 => ({ kind: "invoice", id, label, date: "2025-02-03", amount_cents: cents });
const exp130 = (id: string, label: string, cents: number): Item130 => ({ kind: "expense", id, label, date: "2025-04-15", amount_cents: cents });
const qtr130 = (n: number, cents: number): Item130 => ({ kind: "quarter", id: `T${n}`, label: `T${n} de 2025`, date: `2025-0${3 * n}-30`, amount_cents: cents });

function box130(code: string, group: Box130["group"], amount: number, items: Item130[] = [], components: string[] = []): Box130 {
  return { code, label: `Casilla ${code}`, group, amount_cents: amount, items, components };
}

/** Las siete casillas, como las manda el servidor. */
function seven(opts: { empty?: boolean } = {}): Box130[] {
  if (opts.empty) {
    return [
      box130("01", "rendimiento", 0),
      box130("02", "rendimiento", 0),
      box130("03", "rendimiento", 0, [], ["01", "02"]),
      box130("04", "rendimiento", 0, [], ["03"]),
      box130("05", "pagos", 0),
      box130("06", "pagos", 0),
      box130("07", "resultado", 0, [], ["04", "05", "06"]),
    ];
  }
  return [
    box130("01", "rendimiento", 300_000, [inv130("a", "2025-001", 300_000)]),
    box130("02", "rendimiento", 40_000, [exp130("e", "Papelería", 40_000)]),
    box130("03", "rendimiento", 260_000, [], ["01", "02"]),
    box130("04", "rendimiento", 52_000, [], ["03"]),
    box130("05", "pagos", 5_000, [qtr130(1, 5_000)]),
    box130("06", "pagos", 45_000, [inv130("a", "2025-001", 45_000)]),
    box130("07", "resultado", 2_000, [], ["04", "05", "06"]),
  ];
}

test("?model=130 es el 130 y cualquier otra cosa, o nada, es el 303", () => {
  assert.equal(parseModel({}), "303");
  assert.equal(parseModel({ model: "130" }), "130");
  assert.equal(parseModel({ model: "303" }), "303");
  for (const odd of ["", "abc", "1300", "130 ", " 130", "0130", "13", "٣", "130.0"]) assert.equal(parseModel({ model: odd }), "303", `model=${odd}`);
  assert.equal(parseModel({ model: ["130", "303"] }), "130", "manda el primero si se repite");
  assert.equal(parseModel({ model: ["303", "130"] }), "303");
  assert.equal(parseModel({ model: undefined, year: "2025" }), "303");
});

test("la dirección del 303 no cambia y la del 130 lleva el modelo delante", () => {
  assert.equal(quarterHref(2025, 3), "/trimestres?year=2025&quarter=3");
  assert.equal(quarterHref(2025, 3, "303"), "/trimestres?year=2025&quarter=3");
  assert.equal(quarterHref(2025, 3, "130"), "/trimestres?model=130&year=2025&quarter=3");
  assert.deepEqual(parseQuarterQuery({ model: "130", year: "2025", quarter: "3" }, "2026-11-11"), { year: 2025, quarter: 3 }, "el modelo no estorba al periodo");
});

test("el plazo del 130 se escribe igual que el del 303", () => {
  assert.equal(deadlineBanner({ deadline_status: "plazo_cerrado", deadline: "2026-01-30" }).text, "El plazo terminó el 30 de enero de 2026.");
  assert.equal(deadlineBanner({ deadline_status: "en_curso", deadline: "2026-04-20" }).label, "Trimestre en curso");
});

test("el resultado del 130 con palabras: a ingresar, nada que ingresar (cero o negativo, sin signo) y sin actividad", () => {
  assert.equal(plain(resultText130("a_ingresar", 50_723)), "507,23 € a ingresar");
  assert.equal(resultText130("nada_que_ingresar", 0), "Nada que ingresar este trimestre");
  assert.equal(resultText130("nada_que_ingresar", -153_613), "Nada que ingresar este trimestre");
  assert.ok(!resultText130("nada_que_ingresar", -5).includes("-"), "un resultado negativo no se enseña en el texto: no se arrastra ni se compensa");
  assert.equal(resultText130("sin_actividad", 0), "Sin actividad en este periodo");
});

test("el porcentaje con retención se escribe como información y es nulo si el servidor no lo da", () => {
  assert.equal(withheldShareText(65), "El 65 % de tus ingresos acumulados este año lleva retención.");
  assert.equal(withheldShareText(0), "El 0 % de tus ingresos acumulados este año lleva retención.");
  assert.equal(withheldShareText(100), "El 100 % de tus ingresos acumulados este año lleva retención.");
  assert.equal(withheldShareText(null), null);
});

test("las siete casillas del 130 salen siempre, en tres grupos y en el orden de la hoja, también a cero", () => {
  for (const boxes of [seven(), seven({ empty: true })]) {
    const groups = groupBoxes130(boxes);
    assert.deepEqual(groups.map((g) => [g.group, g.label]), [
      ["rendimiento", "Rendimiento de la actividad (estimación directa)"],
      ["pagos", "Pagos ya hechos y retenciones"],
      ["resultado", "Resultado"],
    ]);
    assert.deepEqual(groups.map((g) => g.boxes.map((b) => b.code)), [["01", "02", "03", "04"], ["05", "06"], ["07"]]);
  }
  assert.deepEqual(groupBoxes130([]), []);
  assert.deepEqual(groupBoxes130([box130("07", "resultado", 0)]).map((g) => g.group), ["resultado"]);
});

test("de qué se compone una casilla derivada del 130", () => {
  const derived = (code: string, components: string[]) => componentsText130({ code, components });
  assert.equal(derived("03", ["01", "02"]), "Casilla 01 menos casilla 02");
  assert.equal(derived("04", ["03"]), "20 % de la casilla 03, si es positiva");
  assert.equal(derived("07", ["04", "05", "06"]), "Casilla 04 menos casillas 05 y 06");
  assert.equal(derived("01", []), null);
  assert.equal(derived("06", []), null);
  assert.equal(derived("09", ["01", "02", "03"]), "Suma de las casillas 01, 02 y 03", "una forma que no conoce se enseña sin inventar");
});

test("el resumen del desplegable del 130 cuenta y nombra facturas, gastos y trimestres", () => {
  const many = (code: string, make: (n: number) => Item130, n: number) => ({ code, items: Array.from({ length: n }, (_, k) => make(k + 1)) });
  const i = (k: number) => inv130(String(k), `F${k}`, 1);
  const e = (k: number) => exp130(String(k), `P${k}`, 1);
  const q = (k: number) => qtr130(k, 1);
  assert.equal(itemSummary130(many("01", i, 0)), null);
  assert.equal(itemSummary130(many("01", i, 1)), "Ver la factura");
  assert.equal(itemSummary130(many("01", i, 3)), "Ver las 3 facturas");
  assert.equal(itemSummary130(many("06", i, 1)), "Ver la factura con retención");
  assert.equal(itemSummary130(many("06", i, 2)), "Ver las 2 facturas con retención");
  assert.equal(itemSummary130(many("02", e, 1)), "Ver el gasto");
  assert.equal(itemSummary130(many("02", e, 4)), "Ver los 4 gastos");
  assert.equal(itemSummary130(many("05", q, 1)), "Ver el trimestre anterior");
  assert.equal(itemSummary130(many("05", q, 3)), "Ver los 3 trimestres anteriores");
});

test("una factura lleva a su detalle, un trimestre anterior a su propio 130 y un gasto a ningún sitio", () => {
  assert.equal(itemHref130({ kind: "invoice", id: "3f2a" }, 2025), "/facturas/3f2a");
  assert.equal(itemHref130({ kind: "expense", id: "3f2a" }, 2025), null);
  assert.equal(itemHref130({ kind: "quarter", id: "T1" }, 2025), "/trimestres?model=130&year=2025&quarter=1");
  assert.equal(itemHref130({ kind: "quarter", id: "T3" }, 2026), "/trimestres?model=130&year=2026&quarter=3");
  for (const odd of ["T0", "T5", "X1", "T", "", "1", "T1.5"]) assert.equal(itemHref130({ kind: "quarter", id: odd }, 2025), null, odd);
});

test("la fila de una casilla del 130 lleva importes con signo, el resumen y los documentos con su enlace", () => {
  const rows = Object.fromEntries(seven().map((b) => [b.code, boxView130(b, 2025)]));
  assert.equal(plain(rows["01"]!.amount), "3000,00 €");
  assert.equal(rows["01"]!.summary, "Ver la factura");
  assert.deepEqual(rows["01"]!.items.map((x) => [x.key, x.label, x.href, plain(x.amount)]), [["invoice-a", "2025-001", "/facturas/a", "3000,00 €"]]);
  assert.equal(rows["01"]!.expensesLink, false);
  assert.equal(rows["02"]!.expensesLink, true);
  assert.equal(rows["02"]!.items[0]?.href, null);
  assert.equal(rows["03"]!.derived, "Casilla 01 menos casilla 02");
  assert.equal(rows["03"]!.summary, null);
  assert.deepEqual(rows["03"]!.items, []);
  assert.equal(rows["05"]!.summary, "Ver el trimestre anterior");
  assert.equal(rows["05"]!.items[0]?.href, "/trimestres?model=130&year=2025&quarter=1");
  assert.equal(rows["06"]!.summary, "Ver la factura con retención");
  assert.deepEqual(Object.entries(rows).filter(([, v]) => v.isResult).map(([k]) => k), ["07"], "solo la 07 es el resultado");
  const negative = boxView130(box130("03", "rendimiento", -252_133, [], ["01", "02"]), 2025);
  assert.ok(negative.amount.includes("-"), "el rendimiento negativo se enseña con su signo");
  assert.equal(plain(negative.amount), "-2521,33 €");
});

test("la fecha de un documento del 130 se escribe en español y el importe es el que aporta a esa casilla", () => {
  const view = boxView130(box130("06", "pagos", -7_500, [inv130("r", "R-2025-001", -7_500)]), 2025);
  assert.equal(view.items[0]?.date, "03/02/2025");
  assert.equal(plain(view.items[0]!.amount), "-75,00 €");
});

test("la fila del 303 es la de siempre: resumen, enlaces e importes según lo que suma la casilla", () => {
  const e = boxView303(box("28", "deducible", "base", 1000, [expense("e", "Papelería", 1000, 210)]));
  assert.equal(e.summary, "Ver el gasto");
  assert.equal(e.expensesLink, true);
  assert.deepEqual(e.items.map((x) => [x.key, x.href, plain(x.amount)]), [["expense-e", null, "10,00 €"]]);
  const v = boxView303(box("09", "devengado", "vat", 53, [invoice("a", "2025-001", 250, 53)]));
  assert.deepEqual(v.items.map((x) => [x.href, plain(x.amount)]), [["/facturas/a", "0,53 €"]]);
  assert.equal(v.expensesLink, false);
  const result = boxView303(box("46", "resultado", null, -157, [], ["27", "45"]));
  assert.equal(result.isResult, true);
  assert.equal(result.derived, "Casilla 27 menos casilla 45");
  assert.equal(boxView303(box("07", "devengado", "base", 0)).isResult, false);
});
