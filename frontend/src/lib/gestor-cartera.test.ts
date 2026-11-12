// SPEC-W-010 §5.5, AC-20 · La cartera y la ficha del gestor: pestañas, páginas, direcciones, textos y el formulario de anotaciones.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PAGE_SIZE,
  TABS,
  TAB_LABEL,
  documentOriginalHref,
  expensesHref,
  fichaHref,
  fieldErrorsFromNoteProblem,
  gestorNoteLinks,
  gestorTaxLinks,
  invitationExpiry,
  invoiceDetailHref,
  invoicePdfHref,
  invoicesHref,
  isOwnerId,
  pageOffset,
  parsePage,
  parseTab,
  pendingText,
  quarterTabHref,
  splitPage,
  toNoteBody,
  valuesFromNoteForm,
} from "./gestor-cartera.ts";
import { describeProblem } from "./problems.ts";

const OWNER = "3f2a9c1e-5b7d-4e8a-9c3b-1a2b3c4d5e6f";
const INVOICE = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";
const code = (n: number) => String.fromCharCode(n);

// --- Pestañas ---------------------------------------------------------------------------------------------------------------------

test("las pestañas son las seis de la ficha, en su orden, con su nombre en español", () => {
  assert.deepEqual([...TABS], ["facturas", "gastos", "documentos", "trimestres", "perfil", "anotaciones"]);
  assert.deepEqual(
    TABS.map((tab) => TAB_LABEL[tab]),
    ["Facturas", "Gastos", "Documentos", "Trimestres", "Perfil y clientes", "Anotaciones"],
  );
});

test("`?tab=` elige una pestaña de la lista; lo demás es Facturas", () => {
  for (const tab of TABS) assert.equal(parseTab({ tab }), tab);
  for (const odd of [undefined, "", "Facturas", "gasto", "../admin", "constructor", "__proto__", "toString", "facturas "]) {
    assert.equal(parseTab({ tab: odd }), "facturas", String(odd));
  }
  assert.equal(parseTab({}), "facturas");
  assert.equal(parseTab({ tab: ["gastos", "perfil"] }), "gastos");
});

// --- Páginas ----------------------------------------------------------------------------------------------------------------------

test("`?pagina=` es un entero de 1 a 10.000; lo demás es la primera página", () => {
  assert.equal(parsePage({ pagina: "1" }), 1);
  assert.equal(parsePage({ pagina: "7" }), 7);
  assert.equal(parsePage({ pagina: "10000" }), 10_000);
  for (const odd of [undefined, "", "0", "-1", "1.5", "abc", "10001", "99999", "100000", "1e3", " 2", "2 ", "0x10"]) {
    assert.equal(parsePage({ pagina: odd }), 1, String(odd));
  }
  assert.equal(parsePage({ pagina: ["3", "4"] }), 3);
});

test("cada página salta las anteriores y se pide una fila de más para saber si hay otra", () => {
  assert.equal(PAGE_SIZE, 50);
  assert.equal(pageOffset(1), 0);
  assert.equal(pageOffset(2), 50);
  assert.equal(pageOffset(10), 450);
  const rows = Array.from({ length: 51 }, (_, index) => index);
  const full = splitPage(rows);
  assert.equal(full.items.length, 50);
  assert.equal(full.hasNext, true);
  assert.equal(full.items.at(-1), 49); // la fila de más no se enseña
  assert.deepEqual(splitPage(rows.slice(0, 50)), { items: rows.slice(0, 50), hasNext: false });
  assert.deepEqual(splitPage([1, 2, 3]), { items: [1, 2, 3], hasNext: false });
  assert.deepEqual(splitPage([]), { items: [], hasNext: false });
});

// --- Direcciones ------------------------------------------------------------------------------------------------------------------

test("las direcciones de la ficha", () => {
  assert.equal(fichaHref(OWNER), `/cartera/${OWNER}?tab=facturas`);
  assert.equal(fichaHref(OWNER, "gastos"), `/cartera/${OWNER}?tab=gastos`);
  assert.equal(invoiceDetailHref(OWNER, INVOICE), `/cartera/${OWNER}/facturas/${INVOICE}`);
  assert.equal(invoicePdfHref(OWNER, INVOICE), `/cartera/${OWNER}/facturas/${INVOICE}/pdf`);
  assert.equal(documentOriginalHref(OWNER, INVOICE), `/cartera/${OWNER}/documentos/${INVOICE}/original`);
});

test("la lista de facturas escribe solo lo que no es lo de por defecto", () => {
  const base = { year: 2026, scope: undefined, paid: undefined } as const;
  assert.equal(invoicesHref(OWNER, base, 1, 2026), `/cartera/${OWNER}?tab=facturas`);
  assert.equal(invoicesHref(OWNER, { ...base, year: 2025 }, 1, 2026), `/cartera/${OWNER}?tab=facturas&year=2025`);
  assert.equal(invoicesHref(OWNER, { ...base, scope: "eu" }, 1, 2026), `/cartera/${OWNER}?tab=facturas&scope=eu`);
  assert.equal(invoicesHref(OWNER, { ...base, paid: true }, 1, 2026), `/cartera/${OWNER}?tab=facturas&paid=paid`);
  assert.equal(invoicesHref(OWNER, { ...base, paid: false }, 1, 2026), `/cartera/${OWNER}?tab=facturas&paid=unpaid`);
  assert.equal(invoicesHref(OWNER, base, 3, 2026), `/cartera/${OWNER}?tab=facturas&pagina=3`);
  assert.equal(invoicesHref(OWNER, { year: 2025, scope: "non_eu", paid: false }, 2, 2026), `/cartera/${OWNER}?tab=facturas&year=2025&scope=non_eu&paid=unpaid&pagina=2`);
});

test("los gastos conservan el cursor, codificado", () => {
  assert.equal(expensesHref(OWNER), `/cartera/${OWNER}?tab=gastos`);
  assert.equal(expensesHref(OWNER, "abc_DEF-123"), `/cartera/${OWNER}?tab=gastos&cursor=abc_DEF-123`);
  assert.equal(expensesHref(OWNER, "a b&c=d"), `/cartera/${OWNER}?tab=gastos&cursor=a%20b%26c%3Dd`);
});

test("un trimestre en la ficha: el 303 sin `model` y el 130 con él", () => {
  assert.equal(quarterTabHref(OWNER, 2025, 2, "303"), `/cartera/${OWNER}?tab=trimestres&year=2025&quarter=2`);
  assert.equal(quarterTabHref(OWNER, 2026, 4, "130"), `/cartera/${OWNER}?tab=trimestres&model=130&year=2026&quarter=4`);
});

test("los enlaces de la hoja del gestor apuntan a su ficha, nunca a las pantallas del autónomo", () => {
  const links = gestorTaxLinks(OWNER);
  assert.equal(links.invoice(INVOICE), `/cartera/${OWNER}/facturas/${INVOICE}`);
  assert.equal(links.quarter(2025, 1, "130"), `/cartera/${OWNER}?tab=trimestres&model=130&year=2025&quarter=1`);
  assert.equal(links.quarter(2025, 1, "303"), `/cartera/${OWNER}?tab=trimestres&year=2025&quarter=1`);
  assert.equal(links.expenses, `/cartera/${OWNER}?tab=gastos`);
  for (const href of [links.invoice(INVOICE), links.quarter(2025, 3, "303"), links.expenses]) {
    assert.ok(href.startsWith(`/cartera/${OWNER}`), href);
    assert.ok(!/^\/(facturas|gastos|trimestres)/.test(href), href);
  }
});

test("las anotaciones del gestor enlazan a la factura y no al gasto (no tiene detalle)", () => {
  const links = gestorNoteLinks(OWNER);
  assert.equal(links.invoice(INVOICE), `/cartera/${OWNER}/facturas/${INVOICE}`);
  assert.equal(links.expense(INVOICE), null);
});

test("solo un UUID es un id de autónomo", () => {
  assert.equal(isOwnerId(OWNER), true);
  for (const odd of ["", "abc", OWNER.toUpperCase(), `${OWNER}/..`, "../admin", null, undefined, 5]) assert.equal(isOwnerId(odd), false, String(odd));
});

// --- Textos -----------------------------------------------------------------------------------------------------------------------

test("los pendientes se dicen con el número y con palabras", () => {
  assert.equal(pendingText(0), "Sin pendientes");
  assert.equal(pendingText(1), "1 documento para revisar");
  assert.equal(pendingText(4), "4 documentos para revisar");
  assert.equal(pendingText(120), "120 documentos para revisar");
});

test("un recuento imposible no se escribe como un número", () => {
  for (const odd of [-1, -4, 1.5, Number.NaN, Number.POSITIVE_INFINITY]) assert.equal(pendingText(odd), "Sin pendientes", String(odd));
});

test("la caducidad de una invitación recibida", () => {
  assert.equal(invitationExpiry("2026-11-26T09:32:00Z"), "Caduca el 26 nov 2026");
  assert.equal(invitationExpiry("2026-12-31T23:30:00Z"), "Caduca el 1 ene 2027"); // hora de Madrid
});

// --- Anotaciones ------------------------------------------------------------------------------------------------------------------

test("del formulario de la anotación solo se lee el texto", () => {
  const form = new Map<string, unknown>([["body", "Revisa el IVA"], ["entity_type", "invoice"], ["entity_id", INVOICE], ["owner_id", OWNER]]);
  assert.deepEqual(valuesFromNoteForm((name) => form.get(name)), { body: "Revisa el IVA" });
  assert.deepEqual(valuesFromNoteForm(() => undefined), { body: "" });
  assert.deepEqual(valuesFromNoteForm(() => new Blob(["x"])), { body: "" });
});

test("un campo con otro nombre no sustituye al texto de la anotación", () => {
  const form = new Map<string, unknown>([["text", "otro"], ["Body", "otro"], ["note", "otro"]]);
  assert.deepEqual(valuesFromNoteForm((name) => form.get(name)), { body: "" });
});

test("el cuerpo recorta, conserva los saltos de línea y quita los controles invisibles", () => {
  assert.deepEqual(toNoteBody({ body: "  Hola  " }, null), { body: "Hola" });
  assert.deepEqual(toNoteBody({ body: `Línea 1${code(10)}Línea 2${code(13)}${code(10)}Línea 3` }, null), { body: `Línea 1${code(10)}Línea 2${code(13)}${code(10)}Línea 3` });
  assert.deepEqual(toNoteBody({ body: `a${code(0)}b${code(0x200b)}c${code(0x202e)}d${code(0x7f)}e` }, null), { body: "a b c d e" });
  assert.deepEqual(toNoteBody({}, null), { body: "" });
});

test("una anotación se liga a una factura solo con un UUID válido", () => {
  assert.deepEqual(toNoteBody({ body: "Mira esto" }, INVOICE), { body: "Mira esto", entity_type: "invoice", entity_id: INVOICE });
  for (const odd of ["", "abc", "../admin", INVOICE.toUpperCase()]) assert.deepEqual(toNoteBody({ body: "Mira esto" }, odd), { body: "Mira esto" }, odd);
});

test("el error del texto va junto al campo; el de lo enlazado, no", () => {
  const body = describeProblem({ status: 422, body: { code: "invalid_note", detail: "El texto debe tener entre 1 y 2.000 caracteres.", fields: [{ field: "body", message: "No válido." }] } });
  assert.deepEqual(fieldErrorsFromNoteProblem(body), { body: "El texto debe tener entre 1 y 2.000 caracteres." });
  const entity = describeProblem({ status: 422, body: { code: "invalid_note", detail: "Lo que enlazas no existe o no es de este autónomo.", fields: [{ field: "entity", message: "No válido." }] } });
  assert.equal(fieldErrorsFromNoteProblem(entity), undefined);
  const bare = describeProblem({ status: 422, body: { code: "invalid_note", detail: "El texto debe tener entre 1 y 2.000 caracteres." } });
  assert.deepEqual(fieldErrorsFromNoteProblem(bare), { body: "El texto debe tener entre 1 y 2.000 caracteres." });
  assert.equal(fieldErrorsFromNoteProblem(describeProblem({ status: 404, body: { code: "not_found", detail: "No existe o no tienes acceso a este recurso." } })), undefined);
  assert.equal(fieldErrorsFromNoteProblem(describeProblem({ status: 503, body: {} })), undefined);
});
