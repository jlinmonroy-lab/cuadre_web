// SPEC-W-007 · Emisión de facturas: inmutables, numeración, mención legal, PDF, QR simulado y rectificativas, en los seis proyectos (Chromium, Firefox y
// WebKit; 390 y 1.440 px). AC-21 a AC-23 y la parte de interfaz de AC-01 a AC-06, AC-09, AC-10, AC-13 a AC-18 y AC-20 en un navegador de verdad (el cálculo, la
// numeración, la inmutabilidad, el PDF y el aislamiento los fijan las pruebas del backend; AC-22 está también en `roles.spec.ts`).
//
// Las pruebas que emiten usan `gastosPage`, la cuenta de `usuario` del worker, y el fixture `biller` la deja lista para facturar (perfil completo con
// retención del 15 % y un cliente de cada tratamiento). Una factura NO se puede borrar ni archivar (RES-03, T7-13): quedan en la cuenta, la numeración
// correlativa es un efecto esperado y ninguna prueba cuenta filas ni números absolutos; cada una localiza lo suyo por un concepto único y lee el número de
// la pantalla. La interfaz no calcula nada: estas pruebas comprueban que enseña lo que decide el servidor. NIF y NIF-IVA son sintéticos.
//
// Next conserva oculta la pantalla anterior al navegar (tras emitir, la lista con su formulario sigue en el DOM): los localizadores piden siempre lo VISIBLE
// y las esperas son por un efecto concreto, no por un texto que ya estaba.
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { Locator, Page, TestInfo } from "@playwright/test";

import { expect, settle, test } from "./helpers/fixtures";
import { shown } from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";

const EURO = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
/** Un importe como lo escribe la interfaz (`1200,00 €`, `-200,00 €`): Playwright compara sin diferencias de espacios (también el de no separación). */
const money = (cents: number): string => EURO.format(cents / 100);
const MINUS = "−";

const MSG_CLIENT = "Elige un cliente.";
const MSG_CONCEPT = "Describe el servicio facturado.";
const MSG_BASE = "Escribe un importe mayor que cero, por ejemplo 1.200,00.";
const MSG_REASON = "Escribe el motivo de la rectificación.";
const MSG_CORRECTED = "Escribe la base corregida (0 si se anula la factura).";
const MSG_FUTURE = "La fecha no puede ser futura.";
const MSG_NO_ADDRESS = "Falta el domicilio del cliente: añádelo para emitir la factura.";
const MSG_EXCEEDS = "Una rectificativa no puede subir el importe: emite una factura nueva.";
const MSG_IRPF = "Elige tu retención de IRPF en el perfil para facturar a una empresa.";
const REVERSE_CHARGE = "Inversión del sujeto pasivo.";

const DETAIL_URL = /\/facturas\/[0-9a-f-]{36}\?emitida=1$/;

/** Hoy (y días antes) en Madrid como `AAAA-MM-DD`: el servidor valida con el reloj de Madrid. */
function madridDate(daysAgo = 0): string {
  const date = new Date(Date.now() - daysAgo * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}
const YEAR = Number(madridDate().slice(0, 4));

/** Un concepto único por prueba y por proyecto: las facturas no se borran y la cuenta del worker las acumula. */
const uniqueConcept = (testInfo: TestInfo): string => `E2E ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;

// --- Localizadores ---------------------------------------------------------------------------------------------------------------

const field = (page: Page, name: string): Locator => shown(page.locator(`#factura-nueva-${name}`));
const fieldError = (page: Page, name: string): Locator => shown(page.locator(`#factura-nueva-${name}-error`));
/** El resumen de errores del formulario «Nueva factura» (el servidor devuelve todos a la vez). */
const summary = (page: Page): Locator => shown(page.locator("form", { has: page.locator("#factura-nueva-concept") }).getByRole("alert"));
const preview = (page: Page): Locator => shown(page.locator("section[aria-labelledby='vista-previa']"));
const issueButton = (page: Page): Locator => shown(page.getByRole("button", { name: "Emitir factura" }));
/** Las filas (tabla) o tarjetas (móvil) de la lista: las dos vistas están en el DOM y solo una se ve. */
const listRows = (page: Page): Locator => shown(page.locator("article, tbody tr"));
const doc = (page: Page): Locator => page.getByRole("article");
const docRow = (page: Page, label: RegExp): Locator => doc(page).getByRole("row", { name: label });
const state = (page: Page, message: string | RegExp): Locator => shown(page.getByRole("status").filter({ hasText: message }));
const rectifySummary = (page: Page): Locator => shown(page.locator("summary", { hasText: "Emitir rectificativa" }));
const rectifyField = (page: Page, name: string): Locator => shown(page.locator(`[id^='rectificar-'][id$='-${name}']`));
const rectifyForm = (page: Page): Locator => shown(page.locator("form", { has: page.locator("[id^='rectificar-'][id$='-reason']") }));

async function openFacturas(page: Page, query = ""): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto(`/facturas${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Facturas" })).toBeVisible();
}

async function openInvoice(page: Page, id: string): Promise<void> {
  await settle(page);
  await page.goto(`/facturas/${id}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/^(Factura|Rectificativa) /);
}

async function openForm(page: Page): Promise<void> {
  if (!(await field(page, "concept").isVisible())) await shown(page.locator("summary", { hasText: "Nueva factura" })).click();
  await expect(field(page, "concept")).toBeVisible();
}

type Draft = { client?: string; base?: string; concept?: string; date?: string; vat?: string };

async function fillForm(page: Page, draft: Draft): Promise<void> {
  await openForm(page);
  if (draft.client !== undefined) await field(page, "client_id").selectOption({ label: draft.client });
  if (draft.date !== undefined) await field(page, "issue_date").fill(draft.date);
  if (draft.base !== undefined) await field(page, "base").fill(draft.base);
  if (draft.concept !== undefined) await field(page, "concept").fill(draft.concept);
  if (draft.vat !== undefined) await field(page, "vat_rate").selectOption(draft.vat);
}

/** Emite por el formulario y espera a la factura nueva; devuelve su número (el que enseña la pantalla). */
async function issueByForm(page: Page, draft: Required<Pick<Draft, "client" | "base" | "concept">> & Draft): Promise<string> {
  await fillForm(page, draft);
  await issueButton(page).click();
  await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
  const heading = page.getByRole("heading", { level: 1 });
  await expect(heading).toContainText(/^Factura \d{4}-\d+$/);
  return ((await heading.innerText()).match(/\d{4}-\d+$/) ?? [""])[0];
}

/** El número de una rectificativa recién emitida (`R-2026-004`). */
async function rectifyingNumber(page: Page): Promise<string> {
  const heading = page.getByRole("heading", { level: 1 });
  await expect(heading).toContainText(/^Rectificativa R-\d{4}-\d+$/);
  return ((await heading.innerText()).match(/R-\d{4}-\d+$/) ?? [""])[0];
}

// --- AC-21 · AC-22 · lista sembrada ----------------------------------------------------------------------------------------------

test("lista (AC-21, AC-22): las facturas sembradas de Alicia, con ámbito y cobro como texto, importes con signo y la rectificativa distinguida", async ({ pageAs }, testInfo) => {
  const page = await pageAs("alicia");
  await openFacturas(page);
  await expect(listRows(page).first()).toBeVisible();
  expect(await listRows(page).count()).toBeGreaterThanOrEqual(6);

  const wide = testInfo.project.use.viewport!.width >= 1280;
  await expect(page.getByRole("table", { name: /Facturas del año/ })).toHaveCount(wide ? 1 : 0);

  const rectifying = listRows(page).filter({ hasText: "R-2026-001" });
  await expect(rectifying).toContainText("Rectificativa");
  await expect(rectifying).toContainText(money(-20_000));
  await expect(rectifying).toContainText(money(-4_200));
  await expect(rectifying).toContainText(`+${money(1_400)}`); // la retención que devuelve se ve con «+»
  await expect(rectifying).toContainText(money(-22_800));

  // Ámbito y cobro siempre escritos (el color solo refuerza).
  for (const label of ["Nacional", "UE", "Fuera de la UE", "Cobrada", "Pendiente"]) {
    await expect(listRows(page).filter({ hasText: label }).first()).toBeVisible();
  }
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
});

test("filtros (AC-21): el año, el ámbito y el cobro viven en la dirección y la lista los obedece", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await openFacturas(page);
  const filters = shown(page.getByRole("form", { name: "Filtros de la lista de facturas" }));

  await filters.getByLabel("Ámbito").selectOption("eu");
  await filters.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page).toHaveURL(/scope=eu/);
  await expect(listRows(page).first()).toBeVisible();
  await expect(listRows(page).filter({ hasText: /Nacional|Fuera de la UE/ })).toHaveCount(0);
  await expect(listRows(page).filter({ hasText: "UE" }).first()).toBeVisible();

  await openFacturas(page, "?paid=paid");
  await expect(listRows(page).filter({ hasText: "Pendiente" })).toHaveCount(0);
  await expect(listRows(page).filter({ hasText: "Cobrada" }).first()).toBeVisible();

  await openFacturas(page, "?paid=unpaid");
  await expect(listRows(page).filter({ hasText: "Cobrada" })).toHaveCount(0);

  await openFacturas(page, "?scope=non_eu&paid=paid"); // ninguna cumple las dos
  await expect(shown(page.getByText("No hay facturas con estos filtros."))).toBeVisible();

  await openFacturas(page, "?year=2020");
  await expect(shown(page.getByText("Todavía no has emitido facturas en 2020."))).toBeVisible();
  await expect(filters.getByLabel("Año")).toHaveValue("2020");

  // Lo desconocido se ignora: ni un año raro ni un ámbito inventado rompen la pantalla.
  await openFacturas(page, "?year=9999&scope=mundo&paid=quizas");
  await expect(listRows(page).first()).toBeVisible();
});

// --- AC-01 a AC-04 · AC-18 · una factura de cada tratamiento ---------------------------------------------------------------------

test("una factura de cada tratamiento (AC-01, AC-02, AC-03, AC-18): lo que enseña la vista previa es lo que se emite", async ({ gastosPage: page, biller }, testInfo) => {
  const cases = [
    // [cliente, base escrita, base, IVA, retención, total, mención]
    { client: biller.clients.national.name, typed: "1.200,00", base: 120_000, vat: 25_200, irpf: 18_000, total: 127_200, note: null, vatLabel: "IVA 21 %" },
    { client: biller.clients.euBusiness.name, typed: "1.500,00", base: 150_000, vat: 0, irpf: 0, total: 150_000, note: REVERSE_CHARGE, vatLabel: "IVA" },
    { client: biller.clients.euPerson.name, typed: "1.000,00", base: 100_000, vat: 21_000, irpf: 0, total: 121_000, note: null, vatLabel: "IVA 21 %" },
    { client: biller.clients.usPerson.name, typed: "1.000,00", base: 100_000, vat: 21_000, irpf: 0, total: 121_000, note: null, vatLabel: "IVA 21 %" },
    { client: biller.clients.mxBusiness.name, typed: "500,00", base: 50_000, vat: 0, irpf: 0, total: 50_000, note: "art. 69 de la Ley del IVA", vatLabel: "IVA" },
  ];
  await openFacturas(page);
  for (const item of cases) {
    const concept = uniqueConcept(testInfo);
    await fillForm(page, { client: item.client, base: item.typed, concept });

    // La vista previa, ANTES de emitir.
    const box = preview(page);
    await expect(box).toContainText("Total a cobrar");
    await expect(box).toContainText(money(item.total));
    if (item.note) await expect(box).toContainText(item.note);

    await issueButton(page).click();
    await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
    await expect(docRow(page, /^Total\b/)).toContainText(money(item.total));
    await expect(docRow(page, /^Base imponible\b/)).toContainText(money(item.base));
    await expect(docRow(page, /^IVA/)).toContainText(item.vat === 0 ? "Sin IVA" : money(item.vat));
    if (item.irpf > 0) await expect(docRow(page, /^Retención/)).toContainText(`${MINUS}${money(item.irpf)}`);
    else await expect(docRow(page, /^Retención/)).toHaveCount(0);
    if (item.note) await expect(doc(page)).toContainText(item.note);
    await expect(doc(page)).toContainText(item.client);
    await expect(doc(page)).toContainText(concept);

    await openFacturas(page);
  }
});

test("vista previa (AC-18, AC-21): cambia con el cliente y con el tipo de IVA, y una base que no se entiende no enseña importes", async ({ gastosPage: page, biller }) => {
  await openFacturas(page);
  await openForm(page);
  await expect(preview(page)).toContainText("Elige un cliente para ver qué impuestos y qué mención llevará la factura.");

  await fillForm(page, { client: biller.clients.national.name, base: "1.200,00" });
  await expect(preview(page)).toContainText("Nacional");
  await expect(preview(page)).toContainText("IVA 21 %");
  await expect(preview(page)).toContainText(money(25_200));
  await expect(preview(page)).toContainText("Retención de IRPF 15 %");
  await expect(preview(page)).toContainText(money(127_200));

  // El selector de IVA solo existe donde hay IVA y cambia la vista previa.
  await expect(field(page, "vat_rate")).toBeVisible();
  await field(page, "vat_rate").selectOption("10");
  await expect(preview(page)).toContainText("IVA 10 %");
  await expect(preview(page)).toContainText(money(12_000));
  await expect(preview(page)).toContainText(money(114_000)); // 1.200 + 120 − 180

  // De un cliente con IVA a otro que también lo admite: no se arrastra el 10 %, vuelve a empezar en el 21 %.
  await field(page, "client_id").selectOption({ label: biller.clients.euPerson.name });
  await expect(preview(page)).toContainText("IVA 21 %");
  await expect(field(page, "vat_rate")).toHaveValue("21");

  // Otro cliente: sin IVA y con mención; el selector desaparece.
  await field(page, "client_id").selectOption({ label: biller.clients.euBusiness.name });
  await expect(preview(page)).toContainText("UE");
  await expect(preview(page)).toContainText("Sin IVA");
  await expect(preview(page)).toContainText(REVERSE_CHARGE);
  await expect(field(page, "vat_rate")).toHaveCount(0);

  // La vista previa es una región que se anuncia al cambiar.
  await expect(preview(page)).toHaveAttribute("aria-live", "polite");

  // Una base ambigua o vacía no inventa importes.
  await field(page, "base").fill("1.200");
  await expect(preview(page)).toContainText("No entendemos la base imponible");
  await expect(preview(page)).not.toContainText("Total a cobrar");
  await field(page, "base").fill("");
  await expect(preview(page)).toContainText("Escribe la base imponible para ver los importes.");
  await expect(preview(page)).not.toContainText("Total a cobrar");
});

test("tipos de IVA y redondeo (AC-04): 10,50 € al 10 % lleva 1,05 € de IVA", async ({ gastosPage: page, biller }, testInfo) => {
  await openFacturas(page);
  await fillForm(page, { client: biller.clients.euPerson.name, base: "10,50", concept: uniqueConcept(testInfo), vat: "10" });
  await expect(preview(page)).toContainText(money(1_155));
  await issueButton(page).click();
  await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
  await expect(docRow(page, /^IVA 10 %/)).toContainText(money(105));
  await expect(docRow(page, /^Total\b/)).toContainText(money(1_155));
});

// --- AC-10 · AC-05 · AC-06 · AC-09 · errores -------------------------------------------------------------------------------------

test("todos los errores a la vez (AC-10): cliente, concepto e importe, uno junto a cada campo y en el orden de la pantalla, sin emitir nada", async ({ gastosPage: page, biller }) => {
  const before = (await biller.invoices.list()).length;
  await openFacturas(page);
  await openForm(page);
  await issueButton(page).click();

  await expect(summary(page)).toBeVisible();
  await expect(summary(page)).toBeFocused();
  const items = summary(page).getByRole("listitem");
  await expect(items).toHaveCount(3);
  await expect(items.nth(0)).toContainText(MSG_CLIENT); // el orden de la pantalla: cliente, concepto e importe
  await expect(items.nth(1)).toContainText(MSG_CONCEPT);
  await expect(items.nth(2)).toContainText(MSG_BASE);
  await expect(fieldError(page, "client_id")).toContainText(MSG_CLIENT);
  await expect(fieldError(page, "concept")).toContainText(MSG_CONCEPT);
  await expect(fieldError(page, "base")).toContainText(MSG_BASE);
  for (const name of ["client_id", "concept", "base"]) {
    await expect(field(page, name)).toHaveAttribute("aria-invalid", "true");
    await expect(field(page, name)).toHaveAttribute("aria-describedby", new RegExp(`factura-nueva-${name}-error`));
  }
  await expect(items.nth(0).getByRole("link")).toHaveAttribute("href", "#factura-nueva-client_id");
  expect((await biller.invoices.list()).length, "no se emitió ninguna").toBe(before);
});

test("importe ambiguo o ilegible (AC-10): «1.200» se rechaza junto a «Base imponible» y lo escrito se conserva; el resumen no repite lo tecleado", async ({ gastosPage: page, biller }, testInfo) => {
  const concept = uniqueConcept(testInfo);
  await openFacturas(page);
  await fillForm(page, { client: biller.clients.national.name, base: "1.200", concept });
  await issueButton(page).click();
  await expect(fieldError(page, "base")).toContainText(MSG_BASE);
  await expect(summary(page)).toBeFocused();
  await expect(summary(page)).not.toContainText(concept);
  await expect(summary(page)).not.toContainText("1.200,00 €");
  await expect(field(page, "concept")).toHaveValue(concept); // lo escrito sobrevive al error
  await expect(field(page, "base")).toHaveValue("1.200");
  await expect(field(page, "client_id")).toHaveValue(biller.clients.national.id);

  await field(page, "base").fill("1.200,00");
  await issueButton(page).click();
  await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
});

test("perfil incompleto (AC-05): se enumera por nombre lo que falta con un enlace a /perfil y no hay formulario", async ({ gastosPage: page, profile }) => {
  void profile; // la cuenta nace sin perfil y `profile` la restaura al empezar y al terminar
  await openFacturas(page);
  const notice = shown(page.getByRole("region", { name: "Completa tu perfil" }));
  await expect(notice).toBeVisible();
  for (const label of ["Nombre o razón social", "NIF", "Domicilio fiscal"]) await expect(notice).toContainText(label);
  await expect(notice.getByRole("link", { name: "Ir a mi perfil" })).toHaveAttribute("href", "/perfil");
  await expect(shown(page.locator("summary", { hasText: "Nueva factura" }))).toHaveCount(0);
});

test("retención sin elegir (AC-05): una empresa nacional da el aviso con enlace al perfil, en la vista previa y al emitir", async ({ gastosPage: page, profile, clients }, testInfo) => {
  await profile.save({ legal_name: "Sin retención E2E", tax_id: "12345678Z", fiscal_address: "Calle Ficticia 1, 28001 Madrid" }); // sin irpf_rate
  const company = await clients.create({ name: "Estudio Norte S.L.", kind: "business", country: "ES", tax_id: "B00000018", address: "Avenida Inventada 4, 28000 Madrid" });
  await openFacturas(page);
  await fillForm(page, { client: company.name, base: "100,00", concept: uniqueConcept(testInfo) });
  await expect(preview(page)).toContainText(MSG_IRPF);
  await expect(preview(page).getByRole("link", { name: "Ir a mi perfil" })).toHaveAttribute("href", "/perfil");

  await issueButton(page).click();
  await expect(summary(page)).toContainText(MSG_IRPF);
  await expect(shown(page.getByRole("link", { name: "Elegir mi retención en el perfil" }))).toHaveAttribute("href", "/perfil");
});

test("cliente sin domicilio o archivado (AC-06): el error sale junto al cliente con enlace a Clientes y el archivado no se ofrece", async ({ gastosPage: page, biller }, testInfo) => {
  await biller.clientsApi.archive(biller.clients.mxBusiness.id);
  await openFacturas(page);
  await openForm(page);
  const options = await field(page, "client_id").locator("option").allInnerTexts();
  expect(options.some((text) => text.includes(biller.clients.mxBusiness.name)), "un cliente archivado no se puede facturar").toBe(false);
  expect(options).toContain(`${biller.clients.noAddress.name} (falta el domicilio)`);

  await fillForm(page, { client: `${biller.clients.noAddress.name} (falta el domicilio)`, base: "100,00", concept: uniqueConcept(testInfo) });
  await expect(preview(page)).toContainText(MSG_NO_ADDRESS); // la vista previa ya lo dice
  await issueButton(page).click();
  await expect(fieldError(page, "client_id")).toContainText(MSG_NO_ADDRESS);
  await expect(field(page, "client_id")).toHaveAttribute("aria-invalid", "true");
  await expect(shown(page.getByRole("link", { name: /Ir a Clientes para completar/ }))).toHaveAttribute("href", "/clientes");
});

test("fechas (AC-09): una fecha futura y una anterior a la última de la serie se rechazan junto a la fecha; corregida, se emite", async ({ gastosPage: page, biller }, testInfo) => {
  // La serie ya tiene una factura de hoy (por la API): una de ayer queda fuera de orden.
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 10_000, issue_date: madridDate() });
  await openFacturas(page);
  const concept = uniqueConcept(testInfo);

  await fillForm(page, { client: biller.clients.national.name, base: "100,00", concept, date: "2099-01-01" });
  await issueButton(page).click();
  await expect(fieldError(page, "issue_date")).toContainText(MSG_FUTURE);
  await expect(field(page, "issue_date")).toHaveAttribute("aria-invalid", "true");

  await field(page, "issue_date").fill(madridDate(1));
  await issueButton(page).click();
  await expect(fieldError(page, "issue_date")).toContainText("La fecha no puede ser anterior");
  await expect(summary(page)).toBeFocused();

  await field(page, "issue_date").fill(madridDate());
  await issueButton(page).click();
  await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
});

// --- AC-11 · AC-16 · AC-17 · AC-20 · emitir y descargar --------------------------------------------------------------------------

test("emitir y descargar (AC-11, AC-16, AC-17, AC-20): detalle bloqueado, PDF descargable, nada sale de la aplicación y la consola no lleva datos", async ({ gastosPage: page, biller }, testInfo) => {
  const external: string[] = [];
  const logged: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && !["localhost", "127.0.0.1"].includes(url.hostname)) external.push(url.hostname);
  });
  page.on("console", (message) => logged.push(message.text()));

  const concept = uniqueConcept(testInfo);
  await openFacturas(page);
  const number = await issueByForm(page, { client: biller.clients.national.name, base: "1.200,00", concept });

  await expect(state(page, `Factura ${number} emitida.`)).toBeVisible();
  await expect(doc(page)).toContainText("Emisora");
  await expect(doc(page)).toContainText("Facturación E2E, diseño gráfico");
  await expect(doc(page)).toContainText("NIF 12345678Z");
  await expect(doc(page)).toContainText(biller.clients.national.name);
  await expect(doc(page)).toContainText("Avenida Inventada 4, 28000 Madrid");
  await expect(shown(page.getByText("Emitida y bloqueada. Para corregirla, emite una rectificativa."))).toBeVisible();
  // Inmutable: ningún campo editable ni botón de borrar en la factura (solo el formulario de rectificar, plegado).
  await expect(doc(page).locator("input, textarea, select, button")).toHaveCount(0);
  await expect(shown(page.getByRole("button", { name: /borrar|eliminar|editar/i }))).toHaveCount(0);

  const link = shown(page.getByRole("link", { name: "Descargar PDF" }));
  await expect(link).toHaveAttribute("href", /\/facturas\/[0-9a-f-]{36}\/pdf$/);
  const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
  expect(download.suggestedFilename()).toBe(`${number}.pdf`);
  const bytes = readFileSync(await download.path());
  expect(bytes.subarray(0, 5).toString("latin1"), "no es un PDF").toBe("%PDF-");
  expect(bytes.length).toBeGreaterThan(1_000);

  expect(external, "ninguna petición debe salir de la aplicación").toEqual([]);
  // AC-20: ni el nombre, ni el NIF, ni el domicilio, ni el concepto en la consola del navegador.
  for (const secret of [concept, biller.clients.national.name, "B00000018", "12345678Z", "Avenida Inventada"]) {
    expect(logged.filter((line) => line.includes(secret)), `la consola lleva «${secret}»`).toEqual([]);
  }
});

const SEEDED_FOR_PROJECT: Record<string, string> = {
  "chromium-390": "2026-001",
  "chromium-1440": "2026-002",
  "firefox-390": "2026-003",
  "firefox-1440": "2026-004",
  "webkit-390": "2026-005",
  "webkit-1440": "R-2026-001",
};

test("generar el PDF (AC-16): una factura sembrada sin PDF lo genera y se puede descargar", async ({ pageAs }, testInfo) => {
  const number = SEEDED_FOR_PROJECT[testInfo.project.name];
  expect(number, `sin factura sembrada para ${testInfo.project.name}`).toBeDefined();
  const page = await pageAs("alicia");
  await openFacturas(page);
  // El enlace de la tarjeta lleva un «Factura » oculto (`sr-only`) y Playwright pulsa en el centro de su primer cuadro, que es ese texto de 1 px: se pulsa sobre
  // el texto visible. Un usuario (ratón, dedo o teclado) no tiene ese problema.
  await shown(page.getByRole("link", { name: new RegExp(`(^|\\s)${number}$`) })).first().click({ position: { x: 12, y: 8 } });
  await expect(page.getByRole("heading", { level: 1 })).toContainText(number!);

  const generate = shown(page.getByRole("button", { name: "Generar PDF" }));
  const download = shown(page.getByRole("link", { name: "Descargar PDF" }));
  if (await generate.isVisible()) {
    await expect(shown(page.getByText("Esta factura aún no tiene PDF."))).toBeVisible();
    await generate.click();
    await expect(download).toBeVisible({ timeout: 30_000 });
    await expect(shown(page.getByText("PDF generado. Ya puedes descargarlo."))).toBeVisible();
  } else {
    // Segunda vuelta sin `supabase db reset`: ya la generó una ejecución anterior. Se anota y se comprueba la descarga.
    testInfo.annotations.push({ type: "aviso", description: `${number} ya tenía PDF: no se pudo ejercitar «Generar PDF» (haz supabase db reset)` });
    await expect(download).toBeVisible();
  }
  const [file] = await Promise.all([page.waitForEvent("download"), download.click()]);
  expect(file.suggestedFilename()).toBe(`${number}.pdf`);
  expect(readFileSync(await file.path()).subarray(0, 5).toString("latin1")).toBe("%PDF-");
});

// --- AC-13 · cobrar --------------------------------------------------------------------------------------------------------------

test("cobrar (AC-13): cobrada y pendiente con su texto y su aviso; una rectificativa no se cobra", async ({ gastosPage: page, biller }, testInfo) => {
  const invoice = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 100_000 });
  await openInvoice(page, invoice.id);
  const status = shown(page.getByRole("list", { name: "Estado" }));
  await expect(status).toContainText("Pendiente");

  await shown(page.getByRole("button", { name: "Marcar como cobrada" })).click();
  await expect(shown(page.getByRole("button", { name: "Marcar como pendiente" }))).toBeVisible();
  await expect(status).toContainText("Cobrada");
  await expect(shown(page.getByText("Factura marcada como cobrada."))).toBeVisible();
  expect((await biller.invoices.byConcept(invoice.concept))?.paid_at, "paid_at se rellena").not.toBeNull();

  await shown(page.getByRole("button", { name: "Marcar como pendiente" })).click();
  await expect(shown(page.getByRole("button", { name: "Marcar como cobrada" }))).toBeVisible();
  await expect(status).toContainText("Pendiente");
  await expect(shown(page.getByText("Factura marcada como pendiente de cobro."))).toBeVisible();
  expect((await biller.invoices.byConcept(invoice.concept))?.paid_at, "paid_at se vacía").toBeNull();
  await expect(docRow(page, /^Total\b/)).toContainText(money(invoice.total_cents)); // el resto de la factura no cambia

  const rectifying = await biller.invoices.rectify(invoice.id, 80_000);
  await openInvoice(page, rectifying.id);
  await expect(shown(page.getByRole("button", { name: /Marcar como/ }))).toHaveCount(0);
  await expect(shown(page.getByRole("heading", { name: "Cobro" }))).toHaveCount(0);
  await expect(shown(page.getByText("Una rectificativa no se corrige", { exact: false }))).toBeVisible();
});

// --- AC-14 · AC-15 · rectificar --------------------------------------------------------------------------------------------------

test("rectificar (AC-14, AC-15): errores a la vez, no subir el importe, una rectificativa por diferencia y anular el resto", async ({ gastosPage: page, biller }, testInfo) => {
  const invoice = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 120_000 });
  await openInvoice(page, invoice.id);
  await rectifySummary(page).click();

  // Sin motivo ni base: los dos errores a la vez, junto a cada campo, y la casilla marcada sobrevive al error.
  await rectifyForm(page).getByRole("button", { name: "Emitir rectificativa" }).click();
  const errors = shown(rectifyForm(page).getByRole("alert"));
  await expect(errors).toBeFocused();
  await expect(errors.getByRole("listitem")).toHaveCount(2);
  await expect(errors).toContainText(MSG_REASON);
  await expect(errors).toContainText(MSG_CORRECTED);
  await expect(rectifyField(page, "reason")).toHaveAttribute("aria-invalid", "true");
  await expect(rectifyField(page, "corrected_base")).toHaveAttribute("aria-invalid", "true");
  await shown(page.getByLabel("Anular por completo", { exact: false })).check();
  await rectifyField(page, "reason").fill("");
  await rectifyForm(page).getByRole("button", { name: "Emitir rectificativa" }).click();
  await expect(shown(rectifyForm(page).getByRole("alert"))).toContainText(MSG_REASON);
  await expect(shown(page.getByLabel("Anular por completo", { exact: false }))).toBeChecked(); // sobrevive al error
  await shown(page.getByLabel("Anular por completo", { exact: false })).uncheck();

  // Subir el importe no se admite.
  await rectifyField(page, "reason").fill("Horas facturadas de más");
  await rectifyField(page, "corrected_base").fill("1.300,00");
  await rectifyForm(page).getByRole("button", { name: "Emitir rectificativa" }).click();
  await expect(shown(rectifyForm(page).getByRole("alert"))).toContainText(MSG_EXCEEDS);

  // 1.000 € sobre 1.200 €: la rectificativa lleva la diferencia.
  await rectifyField(page, "corrected_base").fill("1.000,00");
  await rectifyForm(page).getByRole("button", { name: "Emitir rectificativa" }).click();
  await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
  const number = await rectifyingNumber(page);
  await expect(state(page, `Rectificativa ${number} emitida.`)).toBeVisible();
  await expect(docRow(page, /^Base imponible\b/)).toContainText(money(-20_000));
  await expect(docRow(page, /^IVA 21 %/)).toContainText(money(-4_200));
  await expect(docRow(page, /^Retención/)).toContainText(`+${money(3_000)}`); // devuelve retención
  await expect(docRow(page, /^Total\b/)).toContainText(money(-21_200));
  await expect(doc(page)).toContainText("Rectifica la factura");
  await expect(doc(page)).toContainText("Horas facturadas de más");
  await expect(rectifySummary(page)).toHaveCount(0); // una rectificativa no se rectifica

  // La original dice que está rectificada, con su base vigente, y la lista distingue la rectificativa.
  await openInvoice(page, invoice.id);
  await expect(doc(page)).toContainText(`Rectificada por: ${number}`);
  await expect(doc(page)).toContainText(`Base vigente tras las rectificativas: ${money(100_000)}`);
  await openFacturas(page);
  await expect(listRows(page).filter({ hasText: number }).first()).toContainText("Rectificativa");

  // Anular lo que queda deja la base vigente en 0 y ya no se ofrece rectificar.
  await openInvoice(page, invoice.id);
  await rectifySummary(page).click();
  await rectifyField(page, "reason").fill("Servicio cancelado");
  await shown(page.getByLabel("Anular por completo", { exact: false })).check();
  await rectifyForm(page).getByRole("button", { name: "Emitir rectificativa" }).click();
  await expect(page).toHaveURL(DETAIL_URL, { timeout: 30_000 });
  await expect(docRow(page, /^Base imponible\b/)).toContainText(money(-100_000));
  await openInvoice(page, invoice.id);
  await expect(doc(page)).toContainText(`Base vigente tras las rectificativas: ${money(0)}`);
  await expect(rectifySummary(page)).toHaveCount(0);
});

// --- AC-23 · facturado en el año -------------------------------------------------------------------------------------------------

test("facturado en el año (AC-23): /clientes suma las bases del año (la rectificativa resta), cero en los demás, y enseña las condiciones de cada cliente", async ({ gastosPage: page, biller }, testInfo) => {
  const invoice = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 120_000 });
  await biller.invoices.rectify(invoice.id, 100_000);
  await biller.invoices.issue({ client_id: biller.clients.euPerson.id, concept: uniqueConcept(testInfo), base_cents: 50_000 });

  await settle(page);
  await page.goto("/clientes");
  await expect(page.getByRole("heading", { level: 1, name: "Clientes" })).toBeVisible();
  const row = (name: string): Locator => shown(page.locator("article, tbody tr")).filter({ hasText: name });

  await expect(row(biller.clients.national.name)).toContainText(money(100_000)); // 1.200 − 200
  await expect(row(biller.clients.euPerson.name)).toContainText(money(50_000));
  for (const other of [biller.clients.euBusiness, biller.clients.usPerson, biller.clients.mxBusiness]) {
    await expect(row(other.name)).toContainText(money(0));
  }
  await expect(shown(page.getByText(`Facturado en ${YEAR}`)).first()).toBeVisible();

  await expect(row(biller.clients.national.name)).toContainText("Sus facturas llevarán IVA del 21 % y retención de IRPF del 15 %.");
  await expect(row(biller.clients.euBusiness.name)).toContainText(`Sus facturas irán sin IVA y sin retención, con la mención «${REVERSE_CHARGE}».`);
  await expect(row(biller.clients.euPerson.name)).toContainText("Sus facturas llevarán IVA del 21 % y sin retención.");
  await expect(row(biller.clients.noAddress.name)).toContainText("Añade el domicilio para poder facturarle.");
  await expectNoHorizontalScroll(page);
});

// --- AC-19 (interfaz) · inexistente o ajena --------------------------------------------------------------------------------------

test("factura inexistente o ajena (AC-19): «No encontramos esa factura» y la descarga da 404; un id mal escrito, igual", async ({ gastosPage: page }) => {
  for (const id of ["00000000-0000-4000-8000-000000000000", "no-es-un-id"]) {
    await settle(page);
    await page.goto(`/facturas/${id}`);
    await expect(page.getByRole("heading", { level: 1, name: "No encontramos esa factura" })).toBeVisible();
    await expect(shown(page.getByRole("link", { name: "Volver a Facturas" }))).toHaveAttribute("href", "/facturas");
    const download = await page.request.get(`/facturas/${id}/pdf`);
    expect(download.status()).toBe(404);
    expect(download.headers()["content-type"]).toContain("text/plain");
    expect(await download.text()).toBe("No encontramos esa factura.");
  }
});

// --- AC-21 · interfaz ------------------------------------------------------------------------------------------------------------

test("interfaz (AC-21): sin scroll horizontal, campos etiquetados y sin errores de consola en la lista, el formulario con errores, el detalle y la rectificativa", async ({ gastosPage: page, biller }, testInfo) => {
  const invoice = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 120_000 });
  await openFacturas(page);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  await openForm(page);
  await issueButton(page).click(); // errores a la vez
  await expect(summary(page)).toBeVisible();
  await fillForm(page, { client: biller.clients.euBusiness.name, base: "1.500,00" });
  await expect(preview(page)).toContainText(REVERSE_CHARGE);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  await openInvoice(page, invoice.id);
  await expectNoHorizontalScroll(page);
  await rectifySummary(page).click();
  await expect(rectifyForm(page)).toBeVisible();
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
});

test("interfaz (AC-21): la tabla aparece desde 1.280 px y las tarjetas hasta 1.279, sin scroll horizontal", async ({ gastosPage: page, biller, browserName }, testInfo) => {
  test.skip(browserName !== "chromium", "el ancho límite es el mismo en todos los motores: se comprueba en uno");
  await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 10_000 });
  await openFacturas(page);
  for (const [width, table] of [
    [1279, false],
    [1280, true],
  ] as const) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("table", { name: /Facturas del año/ })).toHaveCount(table ? 1 : 0);
    await expectNoHorizontalScroll(page);
  }
});

test("interfaz (AC-21): con el teclado se llega a todos los campos hasta «Emitir factura», el foco se ve y se puede cobrar sin ratón", async ({ gastosPage: page, biller }, testInfo) => {
  const invoice = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: uniqueConcept(testInfo), base_cents: 10_000 });
  await openFacturas(page);
  await openForm(page);
  const signature = (locator: Locator) =>
    locator.evaluate((el) => {
      const style = getComputedStyle(el);
      return [style.boxShadow, style.outlineStyle, style.outlineWidth, style.outlineColor, style.borderColor].join("|");
    });
  const text = field(page, "concept"); // un campo de texto siempre enseña el foco; el desplegable depende de cómo se enfoque
  const resting = await signature(text);
  await text.focus();
  expect(await signature(text), "el campo no muestra el foco").not.toBe(resting);
  await field(page, "client_id").focus();

  const visited: string[] = [];
  for (let presses = 0; presses < 20; presses++) {
    visited.push(await page.evaluate(() => document.activeElement?.id ?? ""));
    if (await issueButton(page).evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(issueButton(page)).toBeFocused();
  for (const name of ["client_id", "series_id", "issue_date", "base", "concept"]) {
    expect(visited, `el foco no pasó por factura-nueva-${name}`).toContain(`factura-nueva-${name}`);
  }

  // Cobrar sin ratón: foco en el botón y Enter.
  await openInvoice(page, invoice.id);
  const pay = shown(page.getByRole("button", { name: "Marcar como cobrada" }));
  const restingPay = await signature(pay);
  await pay.focus();
  await expect(pay).toBeFocused();
  expect(await signature(pay), "el botón no muestra el foco").not.toBe(restingPay);
  await page.keyboard.press("Enter");
  await expect(shown(page.getByRole("button", { name: "Marcar como pendiente" }))).toBeVisible();
});
