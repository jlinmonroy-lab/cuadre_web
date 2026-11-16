// SPEC-W-013 AC-01 a AC-15 · La pantalla «Reporte mensual», en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px). Las cifras, la comparación, la tendencia
// y las categorías las fijan las pruebas del backend; aquí se comprueba que la interfaz enseña lo que dice el servidor, que cada gráfico tiene su alternativa de
// texto y que no hay scroll horizontal. La interfaz no calcula nada.
//
// La cuenta de `usuario` del worker (`gastosPage`) la comparten otras pruebas y acumula facturas que NO se pueden borrar (RES-03): ninguna prueba espera cifras
// absolutas. Cada una prepara los dos meses anteriores con una serie nueva, los cierra con la CLI del job limitada a esa cuenta y lee lo que dice el servidor
// (`MonthlyApi.report`, el oráculo); la pantalla tiene que enseñar lo mismo.
//
// Localizadores EXACTOS: las filas se identifican por su cabecera de fila con el nombre completo y los importes se comparan celda a celda (`toHaveText`). Nada de
// `hasText` parcial: «2026-001» está dentro de «R-2026-001» y «100,00 €» dentro de «1100,00 €». Con `cacheComponents`, Next conserva ocultas las pantallas ya visitadas:
// los localizadores de CSS y de texto pasan por `shown`.
import type { Locator, Page } from "@playwright/test";

import { API_URL } from "./helpers/env";
import { expect, settle, test } from "./helpers/fixtures";
import { shown } from "./helpers/gastos";
import { madridToday } from "./helpers/invoices";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";
import { MonthlyApi, monthKey } from "./helpers/monthly";
import { prepareReportMonths } from "./helpers/report";
import { signUpAndConfirm, uniqueEmail } from "./helpers/session";

const EURO = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
/** Un importe como lo escribe la interfaz (`1234,50 €`, `-30,00 €`): Playwright compara sin diferencias de espacios (también el de no separación). */
const money = (cents: number): string => EURO.format(cents / 100);

const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const monthName = (month: number): string => MONTHS[month - 1] ?? "";
const title = (month: number): string => monthName(month).replace(/^./, (c) => c.toUpperCase());
const SCOPE_LABEL = { national: "Nacional", eu: "UE", non_eu: "Fuera de la UE" } as const;

/** Puntos básicos a porcentaje con una décima (redondeo hacia arriba en el medio), escrito aquí aparte de la aplicación: el test no importa su código. */
const pct = (bp: number): string => {
  const tenths = Math.floor((Math.abs(bp) + 5) / 10);
  return `${Math.floor(tenths / 10)},${tenths % 10} %`;
};
const variation = (bp: number | null, previousMonth: number): string => {
  if (bp === null) return "sin referencia del mes anterior";
  if (bp === 0) return `sin cambios frente a ${monthName(previousMonth)}`;
  return `${bp > 0 ? "+" : "−"}${pct(bp)} frente a ${monthName(previousMonth)}`;
};
/** El ancho o la alto de una barra, de 0 a 100: escrito aquí aparte de la aplicación (mínimo 1 si hay algo, 0 si no hay nada que dibujar). */
const barPct = (value: number, max: number): number => (value <= 0 || max <= 0 ? 0 : Math.max(1, Math.min(100, Math.round((value * 100) / max))));
const delta = (cents: number, previousMonth: number): string => (cents === 0 ? `sin cambios frente a ${monthName(previousMonth)}` : `${cents > 0 ? "+" : ""}${money(cents)} frente a ${monthName(previousMonth)}`);

// --- Localizadores ---------------------------------------------------------------------------------------------------------------

const section = (page: Page, id: string): Locator => shown(page.locator(`section[aria-labelledby='${id}']`));
const figure = (page: Page, id: string): Locator => shown(page.locator(`figure[aria-labelledby='${id}-titulo']`));

/** Abre «Ver como tabla» de un gráfico y devuelve su tabla. */
async function tableOf(page: Page, id: string): Promise<Locator> {
  const chart = figure(page, id);
  await chart.getByText("Ver como tabla").click();
  const table = chart.getByRole("table");
  await expect(table).toBeVisible();
  return table;
}

/** La fila cuya cabecera tiene exactamente ese nombre (o casa entera con la expresión). */
const rowOf = (table: Locator, name: string | RegExp): Locator =>
  table.getByRole("row").filter({ has: table.page().getByRole("rowheader", { name, exact: true }) });

async function openReporte(page: Page, query = ""): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto(`/reporte${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Reporte mensual" })).toBeVisible();
}

// --- AC-01 · AC-03 · AC-05 · AC-08 · un mes cerrado -------------------------------------------------------------------------------------

test("un mes cerrado enseña lo que dice el servidor: cifras, comparación, ámbitos, clientes, categorías y evolución (AC-01, AC-03, AC-05, AC-08)", async ({
  gastosPage: page,
  biller,
  ledger,
  request,
  gastosUser,
}, testInfo) => {
  test.setTimeout(150_000);
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const { year, month, report } = await prepareReportMonths(biller, ledger, monthly, testInfo);
  expect(report.status).toBe("closed");
  expect(report.comparison, "el mes anterior tiene actividad").not.toBeNull();
  const comparison = report.comparison!;

  await openReporte(page, `?anio=${year}&mes=${month}`);
  await expect(page.getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();
  await expect(shown(page.getByText("Cerrado", { exact: true }))).toBeVisible();

  // Las tres cifras y su comparación con el mes anterior.
  const tile = (label: string): Locator =>
    section(page, "reporte-cifras").locator("div").filter({ has: page.getByRole("term").filter({ hasText: new RegExp(`^${label}$`) }) });
  await expect(tile("Ingresos").getByRole("definition").first()).toHaveText(money(report.total_cents));
  await expect(tile("Gastos").getByRole("definition").first()).toHaveText(money(report.expenses_cents));
  await expect(tile("Rendimiento del mes").getByRole("definition").first()).toHaveText(money(report.result_cents));
  await expect(tile("Ingresos").getByRole("definition").nth(1)).toHaveText(variation(comparison.total_variation_bp, comparison.previous_month));
  await expect(tile("Gastos").getByRole("definition").nth(1)).toHaveText(variation(comparison.expenses_variation_bp, comparison.previous_month));
  await expect(tile("Rendimiento del mes").getByRole("definition").nth(1)).toHaveText(delta(comparison.result_delta_cents, comparison.previous_month));

  // Por ámbito: siempre los tres, con su base y su cuota.
  const scopes = await tableOf(page, "grafico-ambitos");
  await expect(scopes.getByRole("row")).toHaveCount(4);
  for (const scope of report.scopes) {
    const cells = rowOf(scopes, SCOPE_LABEL[scope.scope]).getByRole("cell");
    await expect(cells.nth(0), `base ${scope.scope}`).toHaveText(money(scope.base_cents));
    await expect(cells.nth(1), `cuota ${scope.scope}`).toHaveText(scope.share_bp === null ? "—" : pct(scope.share_bp));
  }

  // La barra segmentada: un tramo por ámbito con base positiva y su `flex-grow` es esa base en céntimos (la proporción la dibuja el navegador).
  const segments = figure(page, "grafico-ambitos").locator("[role='img'] [aria-hidden='true'] > div");
  const positives = report.scopes.filter((scope) => scope.base_cents > 0);
  await expect(segments).toHaveCount(positives.length);
  for (const [index, scope] of positives.entries()) await expect(segments.nth(index), `tramo ${scope.scope}`).toHaveCSS("flex-grow", String(scope.base_cents));

  // Por cliente: una fila por cliente y ámbito, en el orden del servidor.
  const clients = await tableOf(page, "grafico-clientes");
  await expect(clients.getByRole("row")).toHaveCount(report.by_client.length + 1);
  // Un cliente archivado y otro creado después pueden llamarse igual (el fixture `biller` los recrea en cada prueba): se agrupa por nombre, ámbito e importe y la
  // tabla tiene que traer exactamente tantas filas como cada grupo, con celdas exactas.
  const groups = new Map<string, { name: string; scope: keyof typeof SCOPE_LABEL; base: number; count: number }>();
  for (const client of report.by_client) {
    const key = `${client.name}|${client.scope}|${client.base_cents}`;
    const group = groups.get(key) ?? { name: client.name, scope: client.scope, base: client.base_cents, count: 0 };
    group.count += 1;
    groups.set(key, group);
  }
  for (const group of groups.values()) {
    const rows = rowOf(clients, group.name)
      .filter({ has: page.getByRole("cell", { name: SCOPE_LABEL[group.scope], exact: true }) })
      .filter({ has: page.getByRole("cell", { name: money(group.base), exact: true }) });
    await expect(rows, `${group.name} (${group.scope}, ${money(group.base)})`).toHaveCount(group.count);
  }

  // Por categoría: las del servidor, con su número de gastos, y suman lo que cierra el mes mientras el servidor no avise.
  const categories = await tableOf(page, "grafico-categorias");
  await expect(categories.getByRole("row")).toHaveCount(report.expenses_by_category.length + 1);
  for (const category of report.expenses_by_category) {
    const cells = rowOf(categories, category.label).getByRole("cell");
    await expect(cells.nth(0), `gastos de ${category.label}`).toHaveText(String(category.expense_count));
    await expect(cells.nth(1), `importe de ${category.label}`).toHaveText(money(category.expenses_cents));
  }
  expect(report.expenses_by_category.map((c) => c.label)).toEqual(expect.arrayContaining(["Software", "Asesoría", "Otros"]));
  if (report.expenses_note === null) {
    expect(report.expenses_by_category.reduce((sum, c) => sum + c.expenses_cents, 0)).toBe(report.expenses_cents);
    await expect(page.getByRole("status")).toHaveCount(0);
  }
  await expect(figure(page, "grafico-categorias").locator("[role='img']")).toContainText(money(report.expenses_by_category[0]!.expenses_cents)); // la barra lleva su importe escrito
  const categoryBars = figure(page, "grafico-categorias").locator("[role='img'] li");
  await expect(categoryBars).toHaveCount(report.expenses_by_category.length);
  const biggest = Math.max(...report.expenses_by_category.map((category) => category.expenses_cents));
  for (const [index, category] of report.expenses_by_category.entries()) {
    await expect(categoryBars.nth(index).locator("[aria-hidden='true'] > div"), `barra de ${category.label}`).toHaveAttribute("style", new RegExp(`^width:\\s*${barPct(category.expenses_cents, biggest)}%;?$`));
  }

  // La evolución: una fila por mes de la tendencia, la del mes elegido marcada.
  const trend = await tableOf(page, "grafico-evolucion");
  await expect(trend.getByRole("row")).toHaveCount(report.trend.length + 1);
  for (const point of report.trend) {
    const row = rowOf(trend, new RegExp(`^${title(point.month)} de ${point.year}`));
    await expect(row.getByRole("cell").nth(0), `ingresos de ${point.month}/${point.year}`).toHaveText(money(point.total_cents));
    await expect(row.getByRole("cell").nth(1), `gastos de ${point.month}/${point.year}`).toHaveText(money(point.expenses_cents));
  }
  await expect(rowOf(trend, new RegExp(`^${title(month)} de ${year}`))).toHaveAttribute("aria-current", "true");
  // Las columnas: dos por mes (ingresos y gastos) con una escala común, en el orden de la tendencia.
  const columns = figure(page, "grafico-evolucion").locator("[role='img'] ol > li");
  await expect(columns).toHaveCount(report.trend.length);
  const tallest = Math.max(...report.trend.flatMap((point) => [point.total_cents, point.expenses_cents]));
  for (const [index, point] of report.trend.entries()) {
    const bars = columns.nth(index).locator("[aria-hidden='true'] > div");
    await expect(bars.nth(0), `columna de ingresos ${point.month}/${point.year}`).toHaveAttribute("style", new RegExp(`^height:\\s*${barPct(point.total_cents, tallest)}%;?$`));
    await expect(bars.nth(1), `columna de gastos ${point.month}/${point.year}`).toHaveAttribute("style", new RegExp(`^height:\\s*${barPct(point.expenses_cents, tallest)}%;?$`));
  }
});

// --- AC-13 · lo que conviene apartar, sin importe -----------------------------------------------------------------------------------------

test("lo que conviene apartar no lleva ningún importe y enlaza a los borradores del trimestre del mes (AC-13)", async ({ gastosPage: page, request, gastosUser }) => {
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const today = madridToday();
  const [year, month] = [Number(today.slice(0, 4)), Number(today.slice(5, 7))];
  const report = await monthly.report(year, month);

  await openReporte(page, `?anio=${year}&mes=${month}`);
  const apartar = section(page, "reporte-apartar");
  await expect(apartar).toContainText("Orientativo");
  await expect(apartar).not.toContainText(/\d[\d.,]*\s?€/);

  const quarter = `T${report.quarter} de ${report.quarter_year}`;
  const link303 = apartar.getByRole("link", { name: `Ver el borrador del 303 del ${quarter}` });
  const link130 = apartar.getByRole("link", { name: `Ver el borrador del 130 del ${quarter}` });
  await expect(link303).toHaveAttribute("href", `/trimestres?year=${report.quarter_year}&quarter=${report.quarter}`);
  await expect(link130).toHaveAttribute("href", `/trimestres?model=130&year=${report.quarter_year}&quarter=${report.quarter}`);

  await link303.click();
  await expect(page).toHaveURL(new RegExp(`/trimestres\\?year=${report.quarter_year}&quarter=${report.quarter}$`));
  await expect(page.getByRole("heading", { level: 1, name: "Trimestres" })).toBeVisible();
});

// --- AC-10 · el aviso cuando el desglose y el cierre no cuadran --------------------------------------------------------------------------------

test("un gasto atrasado en un mes cerrado se avisa hasta que el cierre se rehace (AC-10)", async ({ gastosPage: page, biller, ledger, request, gastosUser }, testInfo) => {
  test.setTimeout(150_000);
  const monthly = new MonthlyApi(request, gastosUser.email, API_URL);
  const { year, month, concept } = await prepareReportMonths(biller, ledger, monthly, testInfo);

  await ledger.create(`Atrasado ${concept}`, `${monthKey(year, month)}-20`, 1_111, "training"); // sin volver a cerrar
  const stale = await monthly.report(year, month);
  expect(stale.expenses_note, "el servidor avisa del descuadre").not.toBeNull();
  expect(stale.expenses_by_category_total_cents).not.toBe(stale.expenses_cents);

  await openReporte(page, `?anio=${year}&mes=${month}`);
  await expect(shown(page.getByRole("status"))).toHaveText(stale.expenses_note!);
  const categories = await tableOf(page, "grafico-categorias");
  await expect(rowOf(categories, "Formación").getByRole("cell").nth(1)).toHaveText(money(1_111));

  await monthly.close(year, month); // el job vuelve a cerrar el mes: el cierre ya incluye el gasto
  expect((await monthly.report(year, month)).expenses_note).toBeNull();
  await openReporte(page, `?anio=${year}&mes=${month}`);
  await expect(page.getByRole("status")).toHaveCount(0);
});

// --- AC-04 · una cuenta nueva ----------------------------------------------------------------------------------------------------------------

test("una cuenta nueva ve su mes en curso sin referencia y con los textos vacíos (AC-04)", async ({ page, browserName }) => {
  await signUpAndConfirm(page, { name: "Reporte E2E", email: uniqueEmail(browserName) });
  const today = madridToday();
  const [year, month] = [Number(today.slice(0, 4)), Number(today.slice(5, 7))];

  await openReporte(page);
  await expect(page.getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();
  await expect(shown(page.getByText("En curso", { exact: true }))).toBeVisible();
  await expect(shown(page.getByText("No hay un mes anterior con actividad con el que comparar."))).toHaveCount(3);
  await expect(shown(page.getByText("Este mes no hay ingresos positivos que repartir entre ámbitos."))).toBeVisible();
  await expect(shown(page.getByText("No hay facturas emitidas este mes."))).toBeVisible();
  await expect(shown(page.getByText("No hay gastos registrados este mes."))).toBeVisible();
  const trend = await tableOf(page, "grafico-evolucion");
  await expect(trend.getByRole("row")).toHaveCount(2); // la cabecera y el mes en curso
});

// --- AC-11 · AC-14 · el selector y los errores del servidor ------------------------------------------------------------------------------

test("el selector cambia de mes y de año y los errores del servidor se explican (AC-11, AC-14)", async ({ gastosPage: page }) => {
  const year = Number(madridToday().slice(0, 4));
  await openReporte(page);
  await shown(page.getByLabel("Año", { exact: true })).selectOption(String(year - 2));
  await shown(page.getByLabel("Mes", { exact: true })).selectOption("3");
  await page.getByRole("button", { name: "Ver reporte" }).click();
  await expect(page).toHaveURL(new RegExp(`anio=${year - 2}`));
  await expect(page).toHaveURL(/mes=3/);
  await expect(shown(page.getByRole("status"))).toContainText("todavía no tenía actividad"); // el texto del servidor para un mes anterior a la actividad

  await openReporte(page, `?anio=${year + 1}&mes=1`);
  const notice = shown(page.getByRole("status"));
  await expect(notice).toContainText("Ese mes todavía no ha empezado.");
  await notice.getByRole("link", { name: "Ir al año en curso" }).click();
  await expect(page).toHaveURL("/reporte");
  await expect(page.getByRole("heading", { level: 1, name: "Reporte mensual" })).toBeVisible();
});

// --- AC-14 · maqueta y accesibilidad -------------------------------------------------------------------------------------------------------

test("maqueta: cada gráfico tiene su texto alternativo, nada desborda y todos los campos tienen etiqueta (AC-14)", async ({ gastosPage: page }) => {
  await openReporte(page);
  const charts = shown(page.locator("figure [role='img']"));
  await expect(charts).toHaveCount(4);
  await expect(charts.nth(0)).toHaveAttribute("aria-label", /^Ingresos por ámbito en /);
  await expect(charts.nth(1)).toHaveAttribute("aria-label", /^Ingresos por cliente en /);
  await expect(charts.nth(2)).toHaveAttribute("aria-label", /^Gastos por categoría en /);
  await expect(charts.nth(3)).toHaveAttribute("aria-label", /^Ingresos y gastos de los últimos meses/);

  for (const summary of await shown(page.getByText("Ver como tabla")).all()) await summary.click(); // con todas las tablas abiertas
  await expect(shown(page.getByRole("table"))).toHaveCount(4);
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
});

test("sin red: el flujo del reporte no pide nada fuera de localhost (AC-14)", async ({ gastosPage: page }) => {
  const hosts = new Set<string>();
  page.on("request", (request) => {
    if (/^https?:/.test(request.url())) hosts.add(new URL(request.url()).hostname);
  });
  await openReporte(page);
  await shown(page.getByLabel("Mes", { exact: true })).selectOption("1");
  await page.getByRole("button", { name: "Ver reporte" }).click();
  await expect(page).toHaveURL(/mes=1/);
  await settle(page);
  expect([...hosts].filter((host) => !["localhost", "127.0.0.1"].includes(host))).toEqual([]);
});

// --- AC-15 · el enlace desde la contabilidad mensual -----------------------------------------------------------------------------------------

test("el detalle de /mensual enlaza al reporte del mismo mes (AC-15)", async ({ gastosPage: page }) => {
  const today = madridToday();
  const [year, month] = [Number(today.slice(0, 4)), Number(today.slice(5, 7))];
  await settle(page);
  await page.goto(`/mensual?anio=${year}&mes=${month}`);
  await expect(page.getByRole("heading", { level: 1, name: "Contabilidad mensual" })).toBeVisible();
  await page.getByRole("link", { name: `Ver el reporte de ${monthName(month)}` }).click();
  await expect(page).toHaveURL(new RegExp(`/reporte\\?anio=${year}&mes=${month}$`));
  await expect(page.getByRole("heading", { level: 2, name: `${title(month)} de ${year}` })).toBeVisible();
});
