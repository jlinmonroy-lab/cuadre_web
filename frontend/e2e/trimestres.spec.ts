// SPEC-W-008 · Modelo 303 casilla a casilla: la pantalla «Trimestres», en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px). AC-17 a AC-21 y la
// parte de interfaz de AC-01 a AC-07, AC-11 y AC-14 en un navegador de verdad (las reglas fiscales, los cinco trimestres de B.1 y el aislamiento los fijan las
// pruebas del backend; los roles, también `roles.spec.ts`).
//
// La cuenta de `usuario` del worker (`gastosPage`) la comparten `factura.spec.ts` (emite facturas que NO se pueden borrar, RES-03) y las pruebas de Gastos: ninguna
// prueba puede esperar cifras absolutas del trimestre en curso. Cada una lee lo que dice el servidor (`tax.modelo303()`, el oráculo), comprueba que la pantalla
// enseña lo mismo y, cuando emite, que la DIFERENCIA es la esperada y que sus documentos aparecen en su casilla (localizados por número de factura). La interfaz no
// calcula nada. Las facturas que se emiten por la API llevan la fecha de hoy: caen en el trimestre en curso. El único gasto deducible que se puede registrar es el
// de ejemplo del servidor de agentes de E2E (`fixture:invoice_ok`, del 28/10/2026): cae en el T4 de 2026.
//
// La página llega por streaming (renderizado parcial): toda lectura espera a un elemento concreto y los localizadores piden siempre lo VISIBLE (Next conserva oculta
// la pantalla anterior).
import { randomUUID } from "node:crypto";

import type { Locator, Page, TestInfo } from "@playwright/test";

import { API_URL, PEOPLE, SEED_PASSWORD } from "./helpers/env";
import { expect, settle, test, watchBrowserErrors } from "./helpers/fixtures";
import { pdfFile, uniqueName } from "./helpers/files";
import { registerButton, shown, uploadAndOpen } from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";
import { amountsOf, deltas, TaxApi, type Tax303 } from "./helpers/tax";

const EURO = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
/** Un importe como lo escribe la interfaz (`1200,00 €`, `-200,00 €`): Playwright compara sin diferencias de espacios (también el de no separación). */
const money = (cents: number): string => EURO.format(cents / 100);

const TODAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const MONTHS = ["enero a marzo", "abril a junio", "julio a septiembre", "octubre a diciembre"];
const HIDDEN_WHEN_EMPTY = ["01", "03", "04", "06"];
const FIXED_BOXES = ["07", "09", "27", "28", "29", "45", "46", "59", "120"];

/** Un concepto único por prueba y por proyecto: las facturas no se borran y la cuenta del worker las acumula. */
const uniqueConcept = (testInfo: TestInfo): string => `E2E ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;

// --- Localizadores ---------------------------------------------------------------------------------------------------------------

const sheet = (page: Page): Locator => shown(page.locator("section[aria-labelledby='modelo-303']"));
/** La fila de una casilla: su número va en un `<span>` con «Casilla» solo para lectores de pantalla. */
const boxRow = (page: Page, code: string): Locator =>
  sheet(page)
    .locator("li")
    .filter({ has: page.locator("span", { hasText: new RegExp(`^Casilla ${code}$`) }) })
    .first();
const amountOf = (page: Page, code: string): Locator => boxRow(page, code).locator(":scope > span").nth(2);
const detailsOf = (page: Page, code: string): Locator => boxRow(page, code).locator("details");
const quarterNav = (page: Page): Locator => page.getByRole("navigation", { name: "Trimestre", exact: true });
const modelNav = (page: Page): Locator => page.getByRole("navigation", { name: "Modelo", exact: true });
const notice = (page: Page): Locator => shown(page.getByRole("status"));

/** Las casillas que se ven, por número y en el orden de la hoja. */
async function visibleCodes(page: Page): Promise<string[]> {
  const labels = await sheet(page).locator("li > span:first-child").allInnerTexts();
  return labels.map((label) => label.replace("Casilla", "").trim()).filter((code) => /^\d+$/.test(code));
}

async function openTrimestres(page: Page, query = ""): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto(`/trimestres${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Trimestres" })).toBeVisible();
}

/** Abre una casilla con documentos y espera a que el desplegable esté abierto. */
async function openBox(page: Page, code: string): Promise<Locator> {
  const details = detailsOf(page, code);
  await expect(details).toHaveCount(1);
  if (!(await details.evaluate((el) => (el as HTMLDetailsElement).open))) await details.locator("summary").click();
  await expect(details).toHaveAttribute("open", "");
  return details;
}

const resultSentence = (model: Tax303): string => {
  switch (model.result_kind) {
    case "a_ingresar":
      return `${money(model.result_cents)} a ingresar`;
    case "a_compensar":
      return `${money(-model.result_cents)} a compensar en próximos trimestres`;
    case "a_cero":
      return "0,00 €: nada que ingresar ni compensar";
    default:
      return "Sin actividad en este trimestre";
  }
};

const LONG_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
/** `2027-01-30` → `30 de enero de 2027`, como la escribe la pantalla. */
const longDate = (iso: string): string => `${Number(iso.slice(8, 10))} de ${LONG_MONTHS[Number(iso.slice(5, 7)) - 1]} de ${iso.slice(0, 4)}`;

const BANNER = { en_curso: "Trimestre en curso", plazo_abierto: "Plazo abierto", plazo_cerrado: "Plazo cerrado" } as const;

// --- AC-17 · AC-18 · la hoja -----------------------------------------------------------------------------------------------------

test("la hoja (AC-17, AC-18): menú activo, trimestre actual, 303 activo y 130 «Próximamente», plazo con texto y los avisos fijos", async ({ gastosPage: page, tax }) => {
  const model = await tax.modelo303();
  await page.goto("/inicio");
  const menu = page.getByRole("navigation", { name: "Apartados" });
  await shown(menu.getByRole("link", { name: "Trimestres" })).click();
  await expect(page).toHaveURL(/\/trimestres$/);
  await expect(page.getByRole("heading", { level: 1, name: "Trimestres" })).toBeVisible();
  await expect(shown(menu.getByRole("link", { name: "Trimestres" }))).toHaveAttribute("aria-current", "page");

  await expect(quarterNav(page).getByRole("link", { name: new RegExp(`^T${model.quarter}\\b`) })).toHaveAttribute("aria-current", "page");
  await expect(modelNav(page).locator('[aria-current="page"]')).toHaveText("Modelo 303");
  const thirty = modelNav(page).locator('[aria-disabled="true"]');
  await expect(thirty).toContainText("Modelo 130");
  await expect(thirty).toContainText("Próximamente");
  await expect(page.getByRole("heading", { level: 2, name: `T${model.quarter} de ${model.year}: ${MONTHS[model.quarter - 1]}` })).toBeVisible();
  await expect(page.getByText(BANNER[model.deadline_status as keyof typeof BANNER], { exact: true })).toBeVisible();
  await expect(page.getByText(longDate(model.deadline))).toBeVisible(); // la fecha del plazo, la del servidor
  await expect(page.getByRole("heading", { level: 2, name: /Modelo 303/ })).toBeVisible();

  await expect(page.getByRole("heading", { level: 2, name: "Avisos" })).toBeVisible();
  await expect(page.getByText("Borrador orientativo")).toBeVisible();
  await expect(page.getByText("No incluye compensaciones de periodos anteriores")).toBeVisible();
  await expect(page.getByText("Canarias, Ceuta y Melilla")).toBeVisible();
});

// --- AC-13 · AC-17 · lo que enseña la pantalla es lo que dice el servidor ---------------------------------------------------------------

test("lo que enseña la pantalla es lo que dice el servidor (AC-13, AC-17): cada casilla, sus documentos y el resultado", async ({ gastosPage: page, tax, biller }, testInfo) => {
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 100_000 });
  const model = await tax.modelo303();
  await openTrimestres(page);
  await expect(sheet(page)).toBeVisible();

  for (const box of model.boxes) {
    const row = boxRow(page, box.code);
    if (HIDDEN_WHEN_EMPTY.includes(box.code) && box.items.length === 0) {
      await expect(row, `la casilla ${box.code} no tiene documentos y no debe verse`).toHaveCount(0);
      continue;
    }
    await expect(amountOf(page, box.code), `casilla ${box.code}`).toHaveText(money(box.amount_cents));
    if (box.components.length > 0) await expect(row).toContainText(/Suma de las casillas|Igual a la casilla|Casilla 27 menos casilla 45/);
    if (box.items.length > 0) {
      await expect(row.locator("summary")).toContainText(/^Ver (la|el|las \d+|los \d+) (factura|facturas|gasto|gastos)$/);
      const details = await openBox(page, box.code);
      const extra = box.items.some((item) => item.kind === "expense") ? 1 : 0; // «Ir a Gastos»
      await expect(details.locator("ul > li")).toHaveCount(box.items.length + extra);
    } else {
      await expect(row.locator("details")).toHaveCount(0);
    }
  }
  await expect(sheet(page).locator("footer")).toContainText(resultSentence(model));
});

// --- AC-01 · AC-02 · AC-03 · una factura de cada ámbito --------------------------------------------------------------------------

test("una factura de cada ámbito (AC-01, AC-02, AC-03): suben las casillas esperadas y cada factura sale en la suya, con su enlace", async ({ gastosPage: page, tax, biller }, testInfo) => {
  test.setTimeout(120_000);
  const concept = uniqueConcept(testInfo);
  const c = biller.clients;
  const before = await tax.modelo303();
  const issue = (client: { id: string }, base_cents: number, vat_rate?: string) =>
    biller.invoices.issue({ client_id: client.id, concept, base_cents, ...(vat_rate ? { vat_rate } : {}) });
  const national21 = await issue(c.national, 100_000);
  const national10 = await issue(c.national, 50_000, "10");
  const euPerson = await issue(c.euPerson, 20_000);
  const usPerson = await issue(c.usPerson, 30_000);
  const euBusiness = await issue(c.euBusiness, 40_000);
  const mxBusiness = await issue(c.mxBusiness, 25_000);
  const after = await tax.modelo303();

  // El servidor: 21 % de las tres con IVA español, 10 % de la nacional reducida, 59 y 120 sin IVA (y la 27, la suma de las cuotas).
  expect(deltas(before, after)).toMatchObject({
    "01": 0, "03": 0, "04": 50_000, "06": 5_000, "07": 150_000, "09": 31_500, "27": 36_500,
    "28": 0, "29": 0, "45": 0, "46": 36_500, "59": 40_000, "120": 25_000,
  }); // fmt: skip

  await openTrimestres(page);
  for (const [code, cents] of Object.entries(amountsOf(after))) {
    if (HIDDEN_WHEN_EMPTY.includes(code) && cents === 0) continue;
    await expect(amountOf(page, code), `casilla ${code}`).toHaveText(money(cents));
  }

  const placed: [string, string[], { id: string; display_number: string }][] = [
    ["nacional al 21 %", ["07", "09"], national21],
    ["nacional al 10 %", ["04", "06"], national10],
    ["particular de la UE", ["07", "09"], euPerson],
    ["particular de EE. UU.", ["07", "09"], usPerson],
    ["empresa de la UE", ["59"], euBusiness],
    ["empresa de México", ["120"], mxBusiness],
  ];
  const everyBox = ["04", "06", "07", "09", "59", "120"];
  for (const code of everyBox) {
    const details = await openBox(page, code);
    for (const [name, boxes, invoice] of placed) {
      const link = details.getByRole("link", { name: invoice.display_number, exact: true });
      await expect(link, `${name} en la casilla ${code}`).toHaveCount(boxes.includes(code) ? 1 : 0);
    }
  }

  // Con la 59 distinta de cero, el aviso del 349; y una factura lleva a su detalle.
  await expect(page.getByText("también van en el modelo 349")).toBeVisible();
  await detailsOf(page, "59").getByRole("link", { name: euBusiness.display_number, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/facturas/${euBusiness.id}`));
  await expect(page.getByRole("heading", { level: 1 })).toContainText(`Factura ${euBusiness.display_number}`);
});

// --- AC-04 · rectificativa -------------------------------------------------------------------------------------------------------

test("una rectificativa resta en su casilla (AC-04): −200,00 € de base y −42,00 € de cuota, con su número", async ({ gastosPage: page, tax, biller }, testInfo) => {
  test.setTimeout(120_000);
  const before = await tax.modelo303();
  const original = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 120_000 });
  const rectification = await biller.invoices.rectify(original.id, 100_000);
  const after = await tax.modelo303();
  expect(rectification.display_number).toMatch(/^R-\d{4}-\d+$/);
  expect(deltas(before, after)).toMatchObject({ "07": 100_000, "09": 21_000, "27": 21_000 });

  await openTrimestres(page);
  const base = await openBox(page, "07");
  await expect(base.getByRole("listitem").filter({ hasText: original.display_number })).toContainText(money(120_000));
  await expect(base.getByRole("listitem").filter({ hasText: rectification.display_number })).toContainText(money(-20_000));
  await expect(base.getByRole("listitem").filter({ hasText: rectification.display_number })).toContainText(TODAY.split("-").reverse().join("/")); // su fecha
  const vat = await openBox(page, "09");
  await expect(vat.getByRole("listitem").filter({ hasText: original.display_number })).toContainText(money(25_200));
  await expect(vat.getByRole("listitem").filter({ hasText: rectification.display_number })).toContainText(money(-4_200));
  await expect(amountOf(page, "07")).toHaveText(money(amountsOf(after)["07"] ?? 0));
});

// --- AC-05 · gasto deducible y anulado -------------------------------------------------------------------------------------------

test("un gasto deducible entra en la 28 y la 29 y, anulado, sale (AC-05)", async ({ gastosPage: page, tax, ledger }) => {
  test.skip(TODAY < "2026-10-01", "el gasto de ejemplo del servidor de agentes es del 28/10/2026: el T4 de 2026 aún no ha empezado");
  test.setTimeout(120_000);
  await ledger.voidAll();
  await uploadAndOpen(page, pdfFile(uniqueName("factura-nubesoft", "pdf"), "fixture:invoice_ok"));
  await registerButton(page).click();
  await expect(page).toHaveURL(/\/gastos\?aviso=registrado$/);

  const counted = await tax.modelo303(2026, 4);
  expect(amountsOf(counted)).toMatchObject({ "28": 2_479, "29": 521, "45": 521 });
  await openTrimestres(page, "?year=2026&quarter=4");
  await expect(amountOf(page, "28")).toHaveText(money(2_479));
  await expect(amountOf(page, "29")).toHaveText(money(521));
  const details = await openBox(page, "28");
  await expect(details.getByRole("listitem").filter({ hasText: "Nubesoft S.L." })).toContainText(money(2_479));
  await expect(details.getByRole("listitem").filter({ hasText: "Nubesoft S.L." })).toContainText("28/10/2026"); // la fecha del gasto
  await expect(details.getByRole("link", { name: "Ir a Gastos" })).toHaveAttribute("href", "/gastos");

  await ledger.voidAll(); // anulado: ya no cuenta
  const voided = await tax.modelo303(2026, 4);
  expect(amountsOf(voided)).toMatchObject({ "28": 0, "29": 0 });
  await openTrimestres(page, "?year=2026&quarter=4");
  await expect(amountOf(page, "28")).toHaveText(money(0));
  await expect(amountOf(page, "29")).toHaveText(money(0));
  await expect(detailsOf(page, "28")).toHaveCount(0);
  await expect(page.getByText("Nubesoft S.L.")).toHaveCount(0);
});

// --- AC-07 · AC-19 · sin actividad -----------------------------------------------------------------------------------------------

test("un trimestre sin documentos (AC-07, AC-19): «Sin actividad», las nueve casillas fijas a cero y sin aviso del 349", async ({ gastosPage: page, tax }) => {
  const model = await tax.modelo303(2025, 1);
  expect(model.result_kind, "la cuenta del worker no debería tener nada en el T1 de 2025").toBe("sin_actividad");
  await openTrimestres(page, "?year=2025&quarter=1");
  await expect(page.getByRole("heading", { level: 2, name: "T1 de 2025: enero a marzo" })).toBeVisible();
  await expect(sheet(page)).toBeVisible();
  expect(await visibleCodes(page)).toEqual(FIXED_BOXES);
  for (const code of FIXED_BOXES) await expect(amountOf(page, code), `casilla ${code}`).toHaveText(money(0));
  await expect(sheet(page).locator("footer")).toContainText("Sin actividad en este trimestre");
  await expect(page.getByText("Plazo cerrado", { exact: true })).toBeVisible();
  await expect(page.getByText("modelo 349")).toHaveCount(0);
  await expect(sheet(page).locator("details")).toHaveCount(0);
});

// --- AC-17 · el selector ---------------------------------------------------------------------------------------------------------

test("el selector (AC-17): un trimestre por enlace, el año por el formulario conservando el trimestre, y todo sobrevive a recargar", async ({ gastosPage: page, tax }) => {
  const current = await tax.modelo303();
  await openTrimestres(page);
  await quarterNav(page).getByRole("link", { name: /^T1\b/ }).click();
  await expect(page).toHaveURL(new RegExp(`year=${current.year}&quarter=1$`));
  await expect(page.getByRole("heading", { level: 2, name: `T1 de ${current.year}: enero a marzo` })).toBeVisible();
  await expect(quarterNav(page).getByRole("link", { name: /^T1\b/ })).toHaveAttribute("aria-current", "page");

  await shown(page.getByLabel("Año", { exact: true })).selectOption(String(current.year - 1));
  await shown(page.getByRole("button", { name: "Ver", exact: true })).click();
  // El formulario manda `quarter` (campo oculto) antes que `year`: el orden de los parámetros no importa.
  await expect(page).toHaveURL((url) => url.searchParams.get("year") === String(current.year - 1) && url.searchParams.get("quarter") === "1");
  await expect(page.getByRole("heading", { level: 2, name: `T1 de ${current.year - 1}: enero a marzo` })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: `T1 de ${current.year - 1}: enero a marzo` })).toBeVisible();
  await expect(quarterNav(page).getByRole("link", { name: /^T1\b/ })).toHaveAttribute("aria-current", "page");
});

// --- AC-11 · trimestre futuro y direcciones raras ---------------------------------------------------------------------------------

test("un trimestre futuro se explica y una dirección ilegible enseña el trimestre actual (AC-11)", async ({ gastosPage: page, tax }) => {
  const current = await tax.modelo303();
  const title = `T${current.quarter} de ${current.year}: ${MONTHS[current.quarter - 1]}`;
  for (const query of [`?year=${current.year + 1}&quarter=1`, "?year=9998&quarter=4"]) {
    await openTrimestres(page, query);
    await expect(notice(page)).toContainText("Ese trimestre todavía no ha empezado.");
    await expect(sheet(page)).toHaveCount(0);
  }
  await openTrimestres(page, `?year=${current.year + 1}&quarter=1`);
  await expect(quarterNav(page).locator('[aria-disabled="true"]')).toHaveCount(4); // el año que viene no ha empezado
  await page.getByRole("link", { name: "Ir al trimestre actual" }).click();
  await expect(page).toHaveURL(new RegExp(`year=${current.year}&quarter=${current.quarter}$`));
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();

  for (const query of ["?year=abc&quarter=9", "?quarter=5", "?year=1999&quarter=0", "?year=&quarter="]) {
    await openTrimestres(page, query);
    await expect(page.getByRole("heading", { level: 2, name: title }), query).toBeVisible();
    await expect(sheet(page)).toBeVisible();
  }
});

// --- AC-20 · interfaz ------------------------------------------------------------------------------------------------------------

test("interfaz (AC-20): sin scroll horizontal, campos etiquetados, desplegables con teclado, foco visible y sin errores de consola", async ({ gastosPage: page, biller, browserName }, testInfo) => {
  const errors = watchBrowserErrors(page);
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 10_000 });
  await openTrimestres(page);
  await expect(sheet(page)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // Un desplegable se abre y se cierra con el teclado (Enter y Espacio).
  const details = detailsOf(page, "07");
  const summary = details.locator("summary");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(details).toHaveAttribute("open", "");
  await expectNoHorizontalScroll(page);
  await page.keyboard.press("Space");
  await expect(details).not.toHaveAttribute("open", "");

  // Con Tab: año → «Ver» → los trimestres que ya han empezado → el primer desplegable, y el foco se ve.
  const signature = (locator: Locator) =>
    locator.evaluate((el) => {
      const style = getComputedStyle(el);
      return [style.boxShadow, style.outlineStyle, style.outlineWidth, style.outlineColor, style.borderColor].join("|");
    });
  const yearSelect = shown(page.getByLabel("Año", { exact: true }));
  const see = shown(page.getByRole("button", { name: "Ver", exact: true }));
  const restingSee = await signature(see);
  await yearSelect.focus();
  const visited: string[] = [];
  for (let presses = 0; presses < 14; presses++) {
    visited.push(await page.evaluate(() => `${document.activeElement?.tagName}:${(document.activeElement?.textContent ?? "").trim().slice(0, 12)}`));
    if (await page.evaluate(() => document.activeElement?.tagName === "SUMMARY")) break;
    if (visited.length === 2) expect(await signature(see), "«Ver» no muestra el foco").not.toBe(restingSee); // el foco está en «Ver»
    await page.keyboard.press("Tab");
  }
  expect(visited[0]).toMatch(/^SELECT:/);
  expect(visited[1]).toBe("BUTTON:Ver");
  // WebKit no recorre los enlaces con Tab por defecto (como Safari): allí solo se exige llegar al desplegable.
  if (browserName !== "webkit") expect(visited.filter((stop) => /^A:T\d/.test(stop)).length, "el foco no pasó por los trimestres").toBeGreaterThanOrEqual(1);
  expect(visited[visited.length - 1]).toMatch(/^SUMMARY:/);

  // Un trimestre se activa con el teclado: foco en el enlace y Enter.
  const first = quarterNav(page).getByRole("link", { name: /^T1\b/ });
  await first.focus();
  await expect(first).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL((url) => url.searchParams.get("quarter") === "1");
  await expect(sheet(page)).toBeVisible();

  // El aviso de trimestre futuro también cabe y no llevaría ningún campo sin etiqueta.
  await openTrimestres(page, "?year=9998&quarter=4");
  await expect(notice(page)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
  await settle(page);
  expect(errors(), "el navegador registró errores").toEqual([]);
});

// --- T8-03 · sin red -------------------------------------------------------------------------------------------------------------

test("sin red (T8-03): el flujo completo no pide nada fuera de localhost", async ({ gastosPage: page, tax }) => {
  const hosts = new Set<string>();
  page.on("request", (request) => {
    if (/^https?:/.test(request.url())) hosts.add(new URL(request.url()).hostname);
  });
  const current = await tax.modelo303();
  await openTrimestres(page);
  await expect(sheet(page)).toBeVisible();
  await quarterNav(page).getByRole("link", { name: /^T1\b/ }).click();
  await expect(page).toHaveURL(/quarter=1$/);
  await openTrimestres(page, `?year=${current.year + 1}&quarter=1`);
  await expect(notice(page)).toBeVisible();
  await settle(page);
  expect([...hosts].filter((host) => !["localhost", "127.0.0.1"].includes(host))).toEqual([]);
});

// --- AC-14 · cada persona, lo suyo -----------------------------------------------------------------------------------------------

test("cada persona, lo suyo (AC-14): ninguna factura de otra cuenta aparece en el borrador", async ({ gastosPage: page, tax, biller, request }, testInfo) => {
  const mine = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 12_345 });
  const other = new TaxApi(request, PEOPLE.alicia.email, API_URL, SEED_PASSWORD);
  const theirs = await other.modelo303();
  const mineModel = await tax.modelo303();
  const ids = (model: Tax303) => new Set(model.boxes.flatMap((box) => box.items.map((item) => item.id)));
  expect(ids(mineModel).has(mine.id), "mi factura no está en mi borrador").toBe(true);
  expect(ids(theirs).has(mine.id), "mi factura aparece en el borrador de otra cuenta").toBe(false);
  for (const id of ids(theirs)) expect(ids(mineModel).has(id), "una factura de otra cuenta aparece en el mío").toBe(false);

  await openTrimestres(page);
  const details = await openBox(page, "07");
  await expect(details.getByRole("link", { name: mine.display_number, exact: true })).toHaveCount(1);
});
