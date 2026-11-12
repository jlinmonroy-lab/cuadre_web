// SPEC-W-010 hito 4 · Los enlaces de la hoja del 303 y del 130 son configurables (la ficha del gestor pasa los suyos) y, por defecto, siguen siendo los del autónomo.
import assert from "node:assert/strict";
import { test } from "node:test";

import { OWNER_LINKS, boxView130, boxView303, itemHref, itemHref130, quarterHref, type Box130, type Box303, type TaxLinks } from "./tax.ts";

const GESTOR: TaxLinks = {
  invoice: (id) => `/cartera/o/facturas/${id}`,
  quarter: (year, quarter, model) => `/cartera/o?tab=trimestres&model=${model}&year=${year}&quarter=${quarter}`,
  expenses: "/cartera/o?tab=gastos",
};

const box303 = (items: Box303["items"]): Box303 => ({ code: "28", label: "Base", group: "deducible", measure: "base", amount_cents: 1000, items, components: [] }) as Box303;
const box130 = (items: Box130["items"]): Box130 => ({ code: "06", label: "Pagos", group: "pagos", amount_cents: -100, items, components: [] }) as Box130;

test("por defecto, los enlaces son los de las pantallas del autónomo", () => {
  assert.equal(OWNER_LINKS.invoice("3f2a"), "/facturas/3f2a");
  assert.equal(OWNER_LINKS.expenses, "/gastos");
  assert.equal(OWNER_LINKS.quarter(2025, 2, "303"), "/trimestres?year=2025&quarter=2");
  assert.equal(OWNER_LINKS.quarter(2025, 2, "130"), "/trimestres?model=130&year=2025&quarter=2");
  assert.equal(OWNER_LINKS.quarter(2026, 4, "130"), quarterHref(2026, 4, "130"));
  assert.equal(OWNER_LINKS.quarter(2026, 4, "303"), quarterHref(2026, 4));
});

test("con enlaces propios, una factura del 303 va a donde diga el gestor y un gasto, a su lista", () => {
  assert.equal(itemHref({ kind: "invoice", id: "3f2a" }, GESTOR), "/cartera/o/facturas/3f2a");
  assert.equal(itemHref({ kind: "expense", id: "3f2a" }, GESTOR), "/cartera/o?tab=gastos");
  const view = boxView303(box303([{ kind: "invoice", id: "a", label: "2025-001", date: "2025-02-03", base_cents: 100, vat_cents: 21 }]), GESTOR);
  assert.equal(view.items[0]?.href, "/cartera/o/facturas/a");
});

test("un gasto del 303 no lleva enlace propio y la casilla avisa de que hay gastos", () => {
  const view = boxView303(box303([{ kind: "expense", id: "e", label: "Papelería", date: "2025-04-15", base_cents: 100, vat_cents: 21 }]), GESTOR);
  assert.equal(view.items[0]?.href, null);
  assert.equal(view.expensesLink, true);
});

test("en el 130, la factura y el trimestre anterior usan los enlaces del gestor y el gasto no enlaza", () => {
  assert.equal(itemHref130({ kind: "invoice", id: "3f2a" }, 2025, GESTOR), "/cartera/o/facturas/3f2a");
  assert.equal(itemHref130({ kind: "quarter", id: "T2" }, 2025, GESTOR), "/cartera/o?tab=trimestres&model=130&year=2025&quarter=2");
  assert.equal(itemHref130({ kind: "expense", id: "e" }, 2025, GESTOR), null);
  for (const odd of ["T0", "T5", "X1", "", "T1.5"]) assert.equal(itemHref130({ kind: "quarter", id: odd }, 2025, GESTOR), null, odd);
  const view = boxView130(
    box130([
      { kind: "invoice", id: "a", label: "R-2025-001", date: "2025-02-03", amount_cents: -100 },
      { kind: "quarter", id: "T1", label: "T1", date: "2025-03-31", amount_cents: 500 },
    ]),
    2025,
    GESTOR,
  );
  assert.deepEqual(
    view.items.map((item) => item.href),
    ["/cartera/o/facturas/a", "/cartera/o?tab=trimestres&model=130&year=2025&quarter=1"],
  );
});

test("sin enlaces propios, las vistas son idénticas a las de siempre", () => {
  const items303: Box303["items"] = [
    { kind: "invoice", id: "a", label: "2025-001", date: "2025-02-03", base_cents: 100, vat_cents: 21 },
    { kind: "expense", id: "e", label: "Papelería", date: "2025-04-15", base_cents: 100, vat_cents: 21 },
  ];
  assert.deepEqual(boxView303(box303(items303)), boxView303(box303(items303), OWNER_LINKS));
  assert.equal(boxView303(box303(items303)).items[0]?.href, "/facturas/a");
  const items130: Box130["items"] = [
    { kind: "invoice", id: "a", label: "R", date: "2025-02-03", amount_cents: -100 },
    { kind: "quarter", id: "T1", label: "T1", date: "2025-03-31", amount_cents: 500 },
  ];
  assert.deepEqual(boxView130(box130(items130), 2025), boxView130(box130(items130), 2025, OWNER_LINKS));
  assert.deepEqual(
    boxView130(box130(items130), 2025).items.map((item) => item.href),
    ["/facturas/a", "/trimestres?model=130&year=2025&quarter=1"],
  );
});
