// SPEC-W-012 AC-18 · La pantalla «Contabilidad mensual», en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px). Los cierres, la reapertura y la
// coherencia con el 130 los fijan las pruebas del backend; aquí se comprueba que la interfaz enseña lo que dice el servidor (el menú y los roles, también en
// `roles.spec.ts`).
//
// La cuenta de `usuario` del worker (`gastosPage`) la comparten otras pruebas y acumula facturas que NO se pueden borrar (RES-03): ninguna prueba espera cifras
// absolutas. Cada una prepara el mes anterior con una serie nueva (así admite una factura con fecha pasada), una factura y un gasto, lo cierra con la CLI del job
// limitada a esa cuenta y lee lo que dice el servidor (`MonthlyApi`, el oráculo); la pantalla tiene que enseñar lo mismo. La interfaz no calcula nada.
//
// La página llega por streaming: toda lectura espera a un elemento concreto y los localizadores piden siempre lo VISIBLE (a menos de 1.280 px se ven tarjetas y a
// partir de ahí la tabla; las dos están en el DOM y solo una se ve).
import { randomUUID } from "node:crypto";

import type { Locator, Page, TestInfo } from "@playwright/test";

import { API_URL } from "./helpers/env";
import { expect, settle, test } from "./helpers/fixtures";
import { shown } from "./helpers/gastos";
import { madridToday } from "./helpers/invoices";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";
import { MonthlyApi, monthKey, previousMonth, type MonthlyClosing } from "./helpers/monthly";

const EURO = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
/** Un importe como lo escribe la interfaz (`1234,50 €`, `-30,00 €`): Playwright compara sin diferencias de espacios (también el de no separación). */
const money = (cents: number): string => EURO.format(cents / 100);

const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const title = (month: number): string => (MONTHS[month - 1] ?? "").replace(/^./, (c) => c.toUpperCase());

/** Un concepto único por prueba y por proyecto: las facturas no se borran y la cuenta del worker las acumula. */
const uniqueConcept = (testInfo: TestInfo): string => `E2E ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;

// --- Localizadores ---------------------------------------------------------------------------------------------------------------

const months = (page: Page): Locator => page.locator("section[aria-labelledby='meses-del-anio']");
/** La fila (tabla) o la tarjeta (móvil) de un mes. */
const monthRow = (page: Page, month: number): Locator =>
  shown(months(page).locator("tbody tr, article")).filter({ has: page.getByRole("link", { name: new RegExp(`^${title(month)}`) }) });
const detail = (page: Page): Locator => page.locator("section[aria-labelledby='mes-elegido']");

async function openMensual(page: Page, query = ""): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto(`/mensual${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Contabilidad mensual" })).toBeVisible();
}

type Prepared = { year: number; month: number; concept: string; closing: MonthlyClosing };

/** El mes anterior con una factura al cliente nacional, un gasto y su cierre; devuelve lo que el servidor dice de él. */
async function prepareClosedMonth(
  biller: Parameters<Parameters<typeof test>[2]>[0]["biller"],
  ledger: Parameters<Parameters<typeof test>[2]>[0]["ledger"],
  monthly: MonthlyApi,
  testInfo: TestInfo,
): Promise<Prepared> {
  const { year, month } = previousMonth(madridToday());
  const concept = uniqueConcept(testInfo);
  const series = await biller.invoices.createSeries(`E${randomUUID().slice(0, 6).toUpperCase()}`);
  await biller.invoices.issue({
    client_id: biller.clients.national.id,
    concept,
    base_cents: 12_345,
    issue_date: `${monthKey(year, month)}-15`,
    series_id: series.id,
  });
  await ledger.create(`Gasto ${concept}`, `${monthKey(year, month)}-10`, 3_210);
  await monthly.close(year, month);
  return { year, month, concept, closing: await monthly.month(year, month) };
}

// --- Pruebas ----------------------------------------------------------------------------------------------------------------------

test("un mes cerrado enseña las cifras que dice el servidor, su acumulado y sus clientes", async ({ gastosPage: page, biller, ledger, request, gastosUser }, testInfo) => {
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const { year, month, closing } = await prepareClosedMonth(biller, ledger, monthly, testInfo);
  expect(closing.status).toBe("closed");

  await openMensual(page, `?anio=${year}&mes=${month}`);
  const row = monthRow(page, month);
  await expect(row).toContainText("Cerrado");
  for (const cents of [closing.national_cents, closing.total_cents, closing.expenses_cents, closing.ytd_cents]) await expect(row).toContainText(money(cents));

  await expect(detail(page).getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();
  const clients = detail(page).locator("section[aria-labelledby='mes-clientes']");
  const norte = closing.by_client.find((client) => client.name === "Estudio Norte S.L.");
  expect(norte, "el cliente de la factura está en el desglose del servidor").toBeDefined();
  const norteRow = clients.locator("tbody tr").filter({ hasText: "Estudio Norte S.L." });
  await expect(norteRow).toContainText("Nacional");
  await expect(norteRow).toContainText(money(norte?.base_cents ?? 0));
  await expect(clients.locator("tfoot")).toContainText(money(closing.total_cents));

  const result = detail(page).locator("section[aria-labelledby='mes-resultado']");
  await expect(result).toContainText(money(closing.expenses_cents));
  await expect(result.locator("tfoot")).toContainText(money(closing.result_cents));
  await expect(result).toContainText(`Cerrado automáticamente el 1 de ${month === 12 ? `enero de ${year + 1}` : MONTHS[month]}`);
});

test("el mes en curso sale «En curso», calculado en vivo, y su nota dice cuándo se cierra", async ({ gastosPage: page, request, gastosUser }) => {
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const today = madridToday();
  const [year, month] = [Number(today.slice(0, 4)), Number(today.slice(5, 7))];
  const live = await monthly.month(year, month);
  expect(live.status).toBe("in_progress");

  await openMensual(page, `?anio=${year}&mes=${month}`);
  const row = monthRow(page, month);
  await expect(row).toContainText("En curso");
  await expect(row).toContainText(money(live.total_cents));
  await expect(detail(page).getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();
  await expect(detail(page)).toContainText("Este mes se cerrará automáticamente el 1 de");
});

test("elegir otro mes cambia el detalle y la dirección", async ({ gastosPage: page, biller, ledger, request, gastosUser }, testInfo) => {
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const { year, month } = await prepareClosedMonth(biller, ledger, monthly, testInfo);

  await openMensual(page); // sin parámetros: el último mes cerrado
  await expect(detail(page).getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();

  const today = madridToday();
  const current = Number(today.slice(5, 7));
  if (Number(today.slice(0, 4)) === year) {
    await shown(months(page).getByRole("link", { name: new RegExp(`^${title(current)}`) })).click();
    await expect(page).toHaveURL(new RegExp(`anio=${year}&mes=${current}$`));
    await expect(detail(page).getByRole("heading", { level: 2, name: `${title(current)} de ${year}` })).toBeVisible();
  }
  await shown(months(page).getByRole("link", { name: new RegExp(`^${title(month)}`) })).click();
  await expect(page).toHaveURL(new RegExp(`anio=${year}&mes=${month}$`));
  await expect(shown(months(page).locator("a[aria-current='true']"))).toContainText(title(month));
});

test("un gasto atrasado reabre el mes al volver a cerrarlo y la nota lo dice", async ({ gastosPage: page, biller, ledger, request, gastosUser }, testInfo) => {
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const { year, month, concept, closing } = await prepareClosedMonth(biller, ledger, monthly, testInfo);

  await ledger.create(`Atrasado ${concept}`, `${monthKey(year, month)}-20`, 1_111);
  const output = await monthly.close(year, month);
  expect(output).toContain("1 reabiertos");
  const reopened = await monthly.month(year, month);
  expect(reopened.revision).toBe((closing.revision ?? 0) + 1);
  expect(reopened.expenses_cents).toBe(closing.expenses_cents + 1_111);

  await openMensual(page, `?anio=${year}&mes=${month}`);
  await expect(monthRow(page, month)).toContainText(money(reopened.expenses_cents));
  await expect(detail(page)).toContainText(`revisión ${reopened.revision}`);
  await expect(detail(page)).toContainText("Se ha vuelto a cerrar");
});

test("el selector de año cambia de año y un año sin actividad lo explica", async ({ gastosPage: page }) => {
  const year = Number(madridToday().slice(0, 4));
  await openMensual(page);
  await page.getByLabel("Año", { exact: true }).selectOption(String(year - 2));
  await page.getByRole("button", { name: "Ver" }).click();
  await expect(page).toHaveURL(new RegExp(`anio=${year - 2}`));
  await expect(page.getByRole("heading", { level: 2, name: `Meses de ${year - 2}` })).toBeVisible();
  await expect(page.getByText(`No hay meses que mostrar en ${year - 2}`)).toBeVisible();
});

test("un año futuro lo explica con el texto del servidor y ofrece volver al año en curso", async ({ gastosPage: page }) => {
  const year = Number(madridToday().slice(0, 4));
  await openMensual(page, `?anio=${year + 1}`);
  const notice = shown(page.getByRole("status"));
  await expect(notice).toContainText("Ese mes todavía no ha empezado.");
  await notice.getByRole("link", { name: "Ir al año en curso" }).click();
  await expect(page).toHaveURL("/mensual");
  await expect(page.getByRole("heading", { level: 2, name: `Meses de ${year}` })).toBeVisible();
});

test("maqueta: el selector tiene etiqueta y no hay scroll horizontal, con el detalle abierto", async ({ gastosPage: page, biller, ledger, request, gastosUser }, testInfo) => {
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const { year, month } = await prepareClosedMonth(biller, ledger, monthly, testInfo);
  await openMensual(page, `?anio=${year}&mes=${month}`);
  await expect(detail(page).getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
});
