// SPEC-W-009 · Modelo 130 casilla a casilla: la pestaña «Modelo 130» de «Trimestres», en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px). AC-19 a
// AC-23 y la parte de interfaz de AC-01 a AC-10 y AC-14 en un navegador de verdad (las reglas fiscales, los cinco ejercicios de B.1 y el aislamiento los fijan las pruebas
// del backend; los roles, también `roles.spec.ts`).
//
// La cuenta de `usuario` del worker (`gastosPage`) la comparten `factura.spec.ts` (emite facturas que NO se pueden borrar, RES-03), `trimestres.spec.ts` y las pruebas de
// Gastos: ninguna prueba puede esperar cifras absolutas del año en curso. Cada una lee lo que dice el servidor (`tax.modelo130()`, el oráculo), comprueba que la pantalla
// enseña lo mismo y, cuando emite, que la DIFERENCIA es la esperada y que sus documentos aparecen en su casilla (localizados por número de factura o proveedor). La
// interfaz no calcula nada; la regla del 20 %, el acumulado y los pagos anteriores los fijan las pruebas del backend. Las facturas que se emiten por la API llevan la fecha
// de hoy y caen en el trimestre en curso; los gastos sin factura (`ledger.seed`) son del 1 y el 2 de enero de 2026 y cuentan en el 130 del T4 de 2026 (y de todo ese año); el
// único gasto con IVA deducible que se puede registrar es el de ejemplo del servidor de agentes de E2E (`fixture:invoice_ok`, del 28/10/2026).
//
// La página llega por streaming (renderizado parcial): toda lectura espera a un elemento concreto y los localizadores piden siempre lo VISIBLE (Next conserva oculta la
// pantalla anterior, también la hoja del otro modelo).
import { randomUUID } from "node:crypto";

import type { Locator, Page, TestInfo } from "@playwright/test";

import { API_URL, PEOPLE, SEED_PASSWORD } from "./helpers/env";
import { expect, settle, test, watchBrowserErrors } from "./helpers/fixtures";
import { pdfFile, uniqueName } from "./helpers/files";
import { registerButton, shown, text, uploadAndOpen } from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";
import { seededConcept } from "./helpers/ledger";
import { amountsOf, deltas, TaxApi, type Tax130 } from "./helpers/tax";

const EURO = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
/** Un importe como lo escribe la interfaz (`1200,00 €`, `-200,00 €`): Playwright compara sin diferencias de espacios (también el de no separación). */
const money = (cents: number): string => EURO.format(cents / 100);

const TODAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const MONTHS = ["enero a marzo", "abril a junio", "julio a septiembre", "octubre a diciembre"];
const LONG_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
/** `2027-01-30` → `30 de enero de 2027`, como la escribe la pantalla. */
const longDate = (iso: string): string => `${Number(iso.slice(8, 10))} de ${LONG_MONTHS[Number(iso.slice(5, 7)) - 1]} de ${iso.slice(0, 4)}`;
const BANNER = { en_curso: "Trimestre en curso", plazo_abierto: "Plazo abierto", plazo_cerrado: "Plazo cerrado" } as const;
const CODES = ["01", "02", "03", "04", "05", "06", "07"];
/** El T4 de 2026 acumula todo 2026: ahí caen los gastos sembrados del 1 y el 2 de enero y el de ejemplo del 28 de octubre. */
const Y2026 = { year: 2026, quarter: 4 } as const;
const SKIP_BEFORE_2026_Q4 = "los gastos de ejemplo son de 2026 y el T4 de 2026 aún no ha empezado";

/** Un concepto único por prueba y por proyecto: las facturas no se borran y la cuenta del worker las acumula. */
const uniqueConcept = (testInfo: TestInfo): string => `E2E ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;

// --- Localizadores ---------------------------------------------------------------------------------------------------------------

const sheet = (page: Page): Locator => shown(page.locator("section[aria-labelledby='modelo-130']"));
const sheet303 = (page: Page): Locator => shown(page.locator("section[aria-labelledby='modelo-303']"));
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
const modelTab = (page: Page, model: "303" | "130"): Locator => modelNav(page).getByRole("link", { name: `Modelo ${model}`, exact: true });

async function open130(page: Page, query = ""): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto(`/trimestres?model=130${query}`);
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

const resultSentence = (model: Tax130): string => {
  switch (model.result_kind) {
    case "a_ingresar":
      return `${money(model.result_cents)} a ingresar`;
    case "nada_que_ingresar":
      return "Nada que ingresar este trimestre";
    default:
      return "Sin actividad en este periodo";
  }
};

const heading = (year: number, quarter: number): string => `T${quarter} de ${year}: ${MONTHS[quarter - 1]}`;
const ids = (model: Tax130): Set<string> => new Set(model.boxes.flatMap((box) => box.items.filter((item) => item.kind !== "quarter").map((item) => item.id)));

// --- AC-19 · AC-22 · la hoja -----------------------------------------------------------------------------------------------------

test("la hoja (AC-19, AC-22): del menú a la pestaña «Modelo 130», trimestre actual, plazo con texto y los avisos fijos", async ({ gastosPage: page, tax }) => {
  const model = await tax.modelo130();
  await page.goto("/inicio");
  const menu = page.getByRole("navigation", { name: "Apartados" });
  await shown(menu.getByRole("link", { name: "Trimestres" })).click();
  await expect(page).toHaveURL(/\/trimestres$/);
  await expect(modelNav(page).locator('[aria-current="page"]')).toHaveText("Modelo 303"); // sin parámetro, el 303

  await modelTab(page, "130").click(); // la pestaña es un enlace y conserva el año y el trimestre
  await expect(page).toHaveURL(new RegExp(`/trimestres\\?model=130&year=${model.year}&quarter=${model.quarter}$`));
  await expect(modelNav(page).locator('[aria-current="page"]')).toHaveText("Modelo 130");
  await expect(quarterNav(page).getByRole("link", { name: new RegExp(`^T${model.quarter}\\b`) })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 2, name: heading(model.year, model.quarter) })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Modelo 130/ })).toBeVisible();
  await expect(sheet(page)).toContainText("IRPF, pago fraccionado");
  await expect(sheet(page)).toContainText(`T${model.quarter} de ${model.year}, importes acumulados desde enero`);
  await expect(text(page, BANNER[model.deadline_status as keyof typeof BANNER]).first()).toBeVisible();
  await expect(text(page, longDate(model.deadline)).first()).toBeVisible(); // la fecha del plazo, la del servidor

  await expect(page.getByRole("heading", { level: 2, name: "Avisos" })).toBeVisible();
  await expect(text(page, "Borrador orientativo").first()).toBeVisible();
  await expect(text(page, "difícil justificación").first()).toBeVisible();
  await expect(text(page, "vivienda afecta").first()).toBeVisible();
  await expect(text(page, "más del 70 %").first()).toBeVisible();
  for (const note of model.notes) await expect(text(page, note).first()).toBeVisible();
});

// --- AC-19 · AC-23 · lo que enseña la pantalla es lo que dice el servidor --------------------------------------------------------

test("lo que enseña la pantalla es lo que dice el servidor (AC-19, AC-23): cada casilla, sus documentos, el resultado y el porcentaje", async ({ gastosPage: page, tax, biller, ledger }, testInfo) => {
  await ledger.voidAll();
  await ledger.seed(2);
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 100_000 });
  const model = await tax.modelo130();
  await open130(page);
  await expect(sheet(page)).toBeVisible();
  expect(model.boxes.map((box) => box.code)).toEqual(CODES);

  const DERIVED: Record<string, string> = { "03": "Casilla 01 menos casilla 02", "04": "20 % de la casilla 03, si es positiva", "07": "Casilla 04 menos casillas 05 y 06" };
  for (const box of model.boxes) {
    const row = boxRow(page, box.code);
    await expect(amountOf(page, box.code), `casilla ${box.code}`).toHaveText(money(box.amount_cents));
    if (box.components.length > 0) await expect(row).toContainText(DERIVED[box.code] ?? "");
    if (box.items.length > 0) {
      await expect(row.locator("summary")).toContainText(/^Ver (la factura|las \d+ facturas|el gasto|los \d+ gastos|el trimestre anterior|los \d+ trimestres anteriores)( con retención)?$/);
      const details = await openBox(page, box.code);
      const extra = box.items.some((item) => item.kind === "expense") ? 1 : 0; // «Ir a Gastos»
      await expect(details.locator("ul > li")).toHaveCount(box.items.length + extra);
    } else {
      await expect(row.locator("details")).toHaveCount(0);
    }
  }
  await expect(boxRow(page, "06").locator("summary")).toContainText("con retención"); // la factura de arriba lleva el 15 %
  await expect(page.locator("section[aria-labelledby='avisos-130']")).toHaveCount(1); // los avisos de cada modelo llevan su propio id (carga completa: sin pantallas ocultas)
  await expect(page.locator("section[aria-labelledby='avisos-303']")).toHaveCount(0);
  await expect(sheet(page).locator("footer")).toContainText(resultSentence(model));
  if (model.withheld_share_percent === null) await expect(sheet(page)).not.toContainText("lleva retención");
  else await expect(sheet(page)).toContainText(`El ${model.withheld_share_percent} % de tus ingresos acumulados este año lleva retención.`);
});

// --- AC-01 · AC-02 · AC-09 · facturas y rectificativa ----------------------------------------------------------------------------

test("facturas y una rectificativa (AC-01, AC-02, AC-09): suben la 01 y la 06 en lo esperado y cada factura sale en la suya, con su enlace", async ({ gastosPage: page, tax, biller }, testInfo) => {
  test.setTimeout(120_000);
  const concept = uniqueConcept(testInfo);
  const c = biller.clients;
  const before = await tax.modelo130();
  const issue = (client: { id: string }, base_cents: number) => biller.invoices.issue({ client_id: client.id, concept, base_cents });
  const national = await issue(c.national, 100_000); // retención del 15 %: 150,00 €
  const euBusiness = await issue(c.euBusiness, 40_000); // sin retención
  const mxBusiness = await issue(c.mxBusiness, 25_000); // sin retención
  const original = await issue(c.national, 120_000); // retención: 180,00 €
  const rectification = await biller.invoices.rectify(original.id, 100_000); // −200,00 € de base y −30,00 € de retención
  const after = await tax.modelo130();
  expect(rectification.display_number).toMatch(/^R-\d{4}-\d+$/);

  // El servidor: 100.000 + 40.000 + 25.000 + 120.000 − 20.000 de ingresos y 15.000 + 18.000 − 3.000 de retención; ningún gasto y ningún pago anterior nuevo.
  const delta = deltas(before, after);
  expect(delta).toMatchObject({ "01": 265_000, "02": 0, "03": 265_000, "05": 0, "06": 30_000 });

  await open130(page);
  for (const [code, cents] of Object.entries(amountsOf(after))) await expect(amountOf(page, code), `casilla ${code}`).toHaveText(money(cents));

  const income = await openBox(page, "01");
  for (const invoice of [national, euBusiness, mxBusiness, original, rectification]) {
    await expect(income.getByRole("link", { name: invoice.display_number, exact: true }), `${invoice.display_number} en la 01`).toHaveCount(1);
  }
  const row = (details: Locator, invoice: { display_number: string }) => details.getByRole("listitem").filter({ hasText: invoice.display_number });
  await expect(row(income, original)).toContainText(money(120_000));
  await expect(row(income, rectification)).toContainText(money(-20_000));
  await expect(row(income, rectification)).toContainText(TODAY.split("-").reverse().join("/")); // su fecha

  const withheld = await openBox(page, "06"); // solo las facturas que llevan retención, y la rectificativa la devuelve
  for (const [invoice, expected] of [[national, 1], [euBusiness, 0], [mxBusiness, 0], [original, 1], [rectification, 1]] as const) {
    await expect(withheld.getByRole("link", { name: invoice.display_number, exact: true }), `${invoice.display_number} en la 06`).toHaveCount(expected);
  }
  await expect(row(withheld, national)).toContainText(money(15_000));
  await expect(row(withheld, original)).toContainText(money(18_000));
  await expect(row(withheld, rectification)).toContainText(money(-3_000));

  await income.getByRole("link", { name: euBusiness.display_number, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/facturas/${euBusiness.id}`));
  await expect(page.getByRole("heading", { level: 1 })).toContainText(`Factura ${euBusiness.display_number}`);
});

// --- AC-03 · AC-04 · gastos ------------------------------------------------------------------------------------------------------

test("los gastos sin factura suben la 02 por su importe y, anulados, salen (AC-03, AC-04)", async ({ gastosPage: page, tax, ledger }) => {
  test.skip(TODAY < "2026-10-01", SKIP_BEFORE_2026_Q4);
  test.setTimeout(120_000);
  await ledger.voidAll();
  const before = await tax.modelo130(Y2026.year, Y2026.quarter);
  await ledger.seed(2); // 10,01 € y 10,02 €, del 1 y el 2 de enero de 2026
  const after = await tax.modelo130(Y2026.year, Y2026.quarter);
  expect(deltas(before, after)).toMatchObject({ "01": 0, "02": 2_003, "03": -2_003 });

  await open130(page, `&year=${Y2026.year}&quarter=${Y2026.quarter}`);
  await expect(amountOf(page, "02")).toHaveText(money(amountsOf(after)["02"] ?? 0));
  const details = await openBox(page, "02");
  for (const [index, cents] of [[1, 1_001], [2, 1_002]] as const) {
    const gasto = details.getByRole("listitem").filter({ hasText: seededConcept(index) });
    await expect(gasto).toContainText(money(cents)); // lo que aporta a la 02: su importe
    await expect(gasto).toContainText(`0${index}/01/2026`); // la fecha del gasto
    await expect(details.getByRole("link", { name: seededConcept(index), exact: true })).toHaveCount(0); // un gasto no tiene detalle propio
  }
  await expect(details.getByRole("link", { name: "Ir a Gastos" })).toHaveAttribute("href", "/gastos");

  await ledger.voidAll(); // anulados: ya no cuentan ni figuran
  const voided = await tax.modelo130(Y2026.year, Y2026.quarter);
  expect(amountsOf(voided)["02"]).toBe(amountsOf(before)["02"]);
  await open130(page, `&year=${Y2026.year}&quarter=${Y2026.quarter}`);
  await expect(amountOf(page, "02")).toHaveText(money(amountsOf(before)["02"] ?? 0));
  await expect(page.getByText(seededConcept(1))).toHaveCount(0);
  await expect(page.getByText(seededConcept(2))).toHaveCount(0);
});

test("un gasto con IVA deducible suma solo su base a la 02 (AC-03)", async ({ gastosPage: page, tax, ledger }) => {
  test.skip(TODAY < "2026-10-01", "el gasto de ejemplo del servidor de agentes es del 28/10/2026: el T4 de 2026 aún no ha empezado");
  test.setTimeout(120_000);
  await ledger.voidAll();
  const before = await tax.modelo130(Y2026.year, Y2026.quarter);
  await uploadAndOpen(page, pdfFile(uniqueName("factura-nubesoft", "pdf"), "fixture:invoice_ok"));
  await registerButton(page).click();
  await expect(page).toHaveURL(/\/gastos\?aviso=registrado$/);

  const after = await tax.modelo130(Y2026.year, Y2026.quarter);
  expect(deltas(before, after)).toMatchObject({ "02": 2_479 }); // la base: 24,79 €; su IVA deducible (5,21 €) va al 303 y no a esta casilla
  await open130(page, `&year=${Y2026.year}&quarter=${Y2026.quarter}`);
  await expect(amountOf(page, "02")).toHaveText(money(amountsOf(after)["02"] ?? 0));
  const details = await openBox(page, "02");
  const gasto = details.getByRole("listitem").filter({ hasText: "Nubesoft S.L." });
  await expect(gasto).toContainText(money(2_479));
  await expect(gasto).toContainText("28/10/2026"); // la fecha del gasto
  await ledger.voidAll();
});

// --- AC-07 · AC-08 · acumulado y pagos anteriores ---------------------------------------------------------------------------------

test("los pagos de los trimestres anteriores (AC-07, AC-08): cada uno es un documento de la 05 y su enlace lleva al 130 de ese trimestre", async ({ gastosPage: page, tax, biller }, testInfo) => {
  test.setTimeout(120_000);
  const current = await tax.modelo130();
  test.skip(current.quarter === 1, "en el primer trimestre no hay pagos anteriores");
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 10_000 });
  const model = await tax.modelo130();
  const previous = model.boxes.find((box) => box.code === "05");
  expect(previous?.items.map((item) => item.id)).toEqual(Array.from({ length: model.quarter - 1 }, (_, k) => `T${k + 1}`)); // todos, también los de pago 0
  // Lo que pagó cada trimestre es el resultado de ese trimestre, o 0 si salió cero o negativo (el servidor, calculado por separado).
  for (const item of previous?.items ?? []) {
    const quarter = Number(item.id.slice(1));
    const earlier = await tax.modelo130(model.year, quarter);
    expect(item.amount_cents, `pago de T${quarter}`).toBe(Math.max(0, earlier.result_cents));
  }

  await open130(page);
  await expect(amountOf(page, "05")).toHaveText(money(previous?.amount_cents ?? 0));
  await expect(detailsOf(page, "05").locator("summary")).toHaveText(model.quarter === 2 ? "Ver el trimestre anterior" : `Ver los ${model.quarter - 1} trimestres anteriores`);
  const details = await openBox(page, "05");
  for (const item of previous?.items ?? []) {
    const quarter = Number(item.id.slice(1));
    const link = details.getByRole("link", { name: `T${quarter} de ${model.year}`, exact: true });
    await expect(link).toHaveAttribute("href", `/trimestres?model=130&year=${model.year}&quarter=${quarter}`);
    await expect(details.getByRole("listitem").filter({ hasText: `T${quarter} de ${model.year}` })).toContainText(money(item.amount_cents));
  }

  const first = previous?.items[0];
  await details.getByRole("link", { name: `T1 de ${model.year}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`model=130&year=${model.year}&quarter=1$`));
  await expect(page.getByRole("heading", { level: 2, name: heading(model.year, 1) })).toBeVisible();
  const t1 = await tax.modelo130(model.year, 1);
  await expect(amountOf(page, "07")).toHaveText(money(t1.result_cents));
  expect(first?.amount_cents).toBe(Math.max(0, t1.result_cents)); // la casilla 07 de ese trimestre es el pago que figuraba en la 05
});

// --- AC-10 · AC-22 · AC-23 · un periodo sin actividad ---------------------------------------------------------------------------

test("un periodo sin documentos (AC-10, AC-22, AC-23): «Sin actividad», las siete casillas a cero, sin porcentaje y con los avisos", async ({ gastosPage: page, tax }) => {
  const model = await tax.modelo130(2025, 1);
  expect(model.result_kind, "la cuenta del worker no debería tener nada en el T1 de 2025").toBe("sin_actividad");
  expect(model.withheld_share_percent).toBeNull();
  await open130(page, "&year=2025&quarter=1");
  await expect(page.getByRole("heading", { level: 2, name: "T1 de 2025: enero a marzo" })).toBeVisible();
  await expect(sheet(page)).toBeVisible();
  for (const code of CODES) await expect(amountOf(page, code), `casilla ${code}`).toHaveText(money(0));
  await expect(sheet(page).locator("footer")).toContainText("Sin actividad en este periodo");
  await expect(sheet(page)).not.toContainText("lleva retención");
  await expect(text(page, "Plazo cerrado").first()).toBeVisible();
  await expect(sheet(page).locator("details")).toHaveCount(0); // el T1 no tiene ni documentos ni pagos anteriores
  await expect(text(page, "Borrador orientativo").first()).toBeVisible();

  // El T2 sigue sin actividad aunque su 05 liste el T1 (un trimestre anterior que pagó 0 no es un documento).
  const second = await tax.modelo130(2025, 2);
  expect(second.result_kind).toBe("sin_actividad");
  await open130(page, "&year=2025&quarter=2");
  await expect(sheet(page).locator("footer")).toContainText("Sin actividad en este periodo");
  await expect(detailsOf(page, "05").locator("summary")).toHaveText("Ver el trimestre anterior");
  await expect(detailsOf(page, "01")).toHaveCount(0);
});

// --- AC-19 · AC-20 · el selector --------------------------------------------------------------------------------------------------

test("el selector (AC-19, AC-20): trimestre, año y pestañas conservan el modelo, todo sobrevive a recargar y el 303 sigue ahí", async ({ gastosPage: page, tax }) => {
  const current = await tax.modelo130();
  await open130(page);
  await quarterNav(page).getByRole("link", { name: /^T1\b/ }).click();
  await expect(page).toHaveURL(new RegExp(`model=130&year=${current.year}&quarter=1$`));
  await expect(page.getByRole("heading", { level: 2, name: heading(current.year, 1) })).toBeVisible();
  await expect(quarterNav(page).getByRole("link", { name: /^T1\b/ })).toHaveAttribute("aria-current", "page");

  await shown(page.getByLabel("Año", { exact: true })).selectOption(String(current.year - 1));
  await shown(page.getByRole("button", { name: "Ver", exact: true })).click();
  // El formulario manda `quarter` y `model` (campos ocultos) antes que `year`: el orden de los parámetros no importa.
  await expect(page).toHaveURL(
    (url) => url.searchParams.get("model") === "130" && url.searchParams.get("year") === String(current.year - 1) && url.searchParams.get("quarter") === "1",
  );
  await expect(page.getByRole("heading", { level: 2, name: heading(current.year - 1, 1) })).toBeVisible();
  await expect(sheet(page)).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: heading(current.year - 1, 1) })).toBeVisible();
  await expect(sheet(page)).toBeVisible();
  await expect(modelNav(page).locator('[aria-current="page"]')).toHaveText("Modelo 130");

  // La pestaña del 303 quita `model` y enseña la hoja de siempre; la del 130 vuelve con el mismo periodo.
  await modelTab(page, "303").click();
  await expect(page).toHaveURL((url) => !url.searchParams.has("model") && url.searchParams.get("year") === String(current.year - 1) && url.searchParams.get("quarter") === "1");
  await expect(sheet303(page)).toBeVisible();
  await expect(sheet(page)).toHaveCount(0);
  await modelTab(page, "130").click();
  await expect(page).toHaveURL(new RegExp(`model=130&year=${current.year - 1}&quarter=1$`));
  await expect(sheet(page)).toBeVisible();

  // Un modelo que no existe enseña el 303, no un error (AC-20).
  await settle(page);
  await page.goto("/trimestres?model=abc");
  await expect(sheet303(page)).toBeVisible();
  await expect(sheet(page)).toHaveCount(0);
});

// --- AC-14 · trimestre futuro y direcciones raras ---------------------------------------------------------------------------------

test("un trimestre futuro se explica y una dirección ilegible enseña el trimestre actual del 130 (AC-14)", async ({ gastosPage: page, tax }) => {
  const current = await tax.modelo130();
  const title = heading(current.year, current.quarter);
  for (const query of [`&year=${current.year + 1}&quarter=1`, "&year=9998&quarter=4"]) {
    await open130(page, query);
    await expect(notice(page)).toContainText("Ese trimestre todavía no ha empezado.");
    await expect(sheet(page)).toHaveCount(0);
  }
  await open130(page, `&year=${current.year + 1}&quarter=1`);
  await expect(quarterNav(page).locator('[aria-disabled="true"]')).toHaveCount(4); // el año que viene no ha empezado
  await page.getByRole("link", { name: "Ir al trimestre actual" }).click();
  await expect(page).toHaveURL(new RegExp(`model=130&year=${current.year}&quarter=${current.quarter}$`)); // conserva el modelo
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await expect(sheet(page)).toBeVisible();

  for (const query of ["&year=abc&quarter=9", "&quarter=5", "&year=1999&quarter=0", "&year=&quarter="]) {
    await open130(page, query);
    await expect(page.getByRole("heading", { level: 2, name: title }), query).toBeVisible();
    await expect(sheet(page), query).toBeVisible();
  }
});

// --- AC-21 · interfaz -------------------------------------------------------------------------------------------------------------

test("interfaz (AC-21): sin scroll horizontal, campos etiquetados, desplegables y pestañas con teclado, foco visible y sin errores de consola", async ({ gastosPage: page, biller, browserName }, testInfo) => {
  const errors = watchBrowserErrors(page);
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 10_000 });
  await open130(page);
  await expect(sheet(page)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // Un desplegable se abre y se cierra con el teclado (Enter y Espacio).
  const details = detailsOf(page, "01");
  const summary = details.locator("summary");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(details).toHaveAttribute("open", "");
  await expectNoHorizontalScroll(page);
  await page.keyboard.press("Space");
  await expect(details).not.toHaveAttribute("open", "");

  // Con Tab: año → «Ver» → los trimestres que ya han empezado → las dos pestañas de modelo → el primer desplegable, y el foco se ve.
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
  for (let presses = 0; presses < 16; presses++) {
    visited.push(await page.evaluate(() => `${document.activeElement?.tagName}:${(document.activeElement?.textContent ?? "").trim().slice(0, 12)}`));
    if (await page.evaluate(() => document.activeElement?.tagName === "SUMMARY")) break;
    if (visited.length === 2) expect(await signature(see), "«Ver» no muestra el foco").not.toBe(restingSee); // el foco está en «Ver»
    await page.keyboard.press("Tab");
  }
  expect(visited[0]).toMatch(/^SELECT:/);
  expect(visited[1]).toBe("BUTTON:Ver");
  // WebKit no recorre los enlaces con Tab por defecto (como Safari): allí solo se exige llegar al desplegable.
  if (browserName !== "webkit") {
    expect(visited.filter((stop) => /^A:T\d/.test(stop)).length, "el foco no pasó por los trimestres").toBeGreaterThanOrEqual(1);
    expect(visited, "el foco no pasó por las pestañas de modelo").toEqual(expect.arrayContaining(["A:Modelo 303", "A:Modelo 130"]));
  }
  expect(visited[visited.length - 1]).toMatch(/^SUMMARY:/);

  // Un trimestre y un modelo se activan con el teclado: foco en el enlace y Enter.
  const first = quarterNav(page).getByRole("link", { name: /^T1\b/ });
  await first.focus();
  await expect(first).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL((url) => url.searchParams.get("quarter") === "1" && url.searchParams.get("model") === "130");
  await expect(sheet(page)).toBeVisible();
  const tab303 = modelTab(page, "303");
  await tab303.focus();
  await expect(tab303).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL((url) => !url.searchParams.has("model"));
  await expect(sheet303(page)).toBeVisible();

  // El aviso de trimestre futuro también cabe y no llevaría ningún campo sin etiqueta.
  await open130(page, "&year=9998&quarter=4");
  await expect(notice(page)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
  await settle(page);
  expect(errors(), "el navegador registró errores").toEqual([]);
});

// --- T8-03 · sin red --------------------------------------------------------------------------------------------------------------

test("sin red: el flujo completo del 130 no pide nada fuera de localhost", async ({ gastosPage: page, tax }) => {
  const hosts = new Set<string>();
  page.on("request", (request) => {
    if (/^https?:/.test(request.url())) hosts.add(new URL(request.url()).hostname);
  });
  const current = await tax.modelo130();
  await open130(page);
  await expect(sheet(page)).toBeVisible();
  await quarterNav(page).getByRole("link", { name: /^T1\b/ }).click();
  await expect(page).toHaveURL(/quarter=1$/);
  await open130(page, `&year=${current.year + 1}&quarter=1`);
  await expect(notice(page)).toBeVisible();
  await settle(page);
  expect([...hosts].filter((host) => !["localhost", "127.0.0.1"].includes(host))).toEqual([]);
});

// --- AC-16 · cada persona, lo suyo ------------------------------------------------------------------------------------------------

test("cada persona, lo suyo (AC-16): ninguna factura de otra cuenta aparece en el borrador del 130", async ({ gastosPage: page, tax, biller, request }, testInfo) => {
  const mine = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 12_345 });
  const other = new TaxApi(request, PEOPLE.alicia.email, API_URL, SEED_PASSWORD);
  const theirs = await other.modelo130();
  const mineModel = await tax.modelo130();
  expect(ids(mineModel).has(mine.id), "mi factura no está en mi borrador").toBe(true);
  expect(ids(theirs).has(mine.id), "mi factura aparece en el borrador de otra cuenta").toBe(false);
  for (const id of ids(theirs)) expect(ids(mineModel).has(id), "una factura de otra cuenta aparece en el mío").toBe(false);

  await open130(page);
  const details = await openBox(page, "01");
  await expect(details.getByRole("link", { name: mine.display_number, exact: true })).toHaveCount(1);
});
