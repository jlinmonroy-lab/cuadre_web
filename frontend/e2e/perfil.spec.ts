// SPEC-W-005 · Perfil personal y del negocio y series de facturación, en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px).
// AC-01 a AC-07, AC-09 a AC-16, AC-18 y AC-19 en un navegador de verdad (AC-08 y AC-17 son de la API y la base; AC-20 está en `roles.spec.ts`).
//
// Usan `gastosPage`, la cuenta de `usuario` del worker, que comparten estas pruebas y las de Gastos: el fixture `profile` restaura el perfil
// (vacío, sin logo y solo la serie del año) al empezar y al terminar, porque las de Gastos esperan un perfil vacío (T5-11). La interfaz no valida
// nada fiscal: estas pruebas comprueban que enseña lo que decide el servidor. NIF e IBAN son sintéticos con dígitos de control válidos.
import { randomUUID } from "node:crypto";

import type { Locator, Page } from "@playwright/test";

import { expect, settle, test } from "./helpers/fixtures";
import { pdfFile, pngFile, uniqueName } from "./helpers/files";
import { field, shown, text, uploadAndOpen } from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";

const NIF = "12345678Z";
const OTHER_NIF = "01230956L";
const IBAN = "ES91 2100 0418 4502 0005 1332";
const NAME = "Alicia E2E, diseño gráfico";
const ADDRESS = "Calle Ficticia 1, 28001 Madrid";
const VALID = { legal_name: NAME, tax_id: NIF, fiscal_address: ADDRESS };
const MISMATCH = "La factura no va a tu NIF: el destinatario no coincide con el de tu perfil.";

const YEAR = new Date().getFullYear();

async function openPerfil(page: Page): Promise<void> {
  await settle(page);
  await page.goto("/perfil");
  await expect(page.getByRole("heading", { level: 1, name: "Perfil" })).toBeVisible();
}

const save = (page: Page): Locator => page.getByRole("button", { name: "Guardar", exact: true });
/** El resumen de errores del formulario del perfil (el servidor devuelve todos a la vez). */
const summary = (page: Page): Locator => page.getByRole("alert").filter({ hasText: /Revisa los campos marcados|Revisa estos datos/ });
const saved = (page: Page): Locator => text(page, "Cambios guardados.");
const error = (page: Page, name: string): Locator => shown(page.locator(`#perfil-${name}-error`));
const state = (page: Page, message: string | RegExp): Locator => page.getByRole("status").filter({ hasText: message });

async function fillValid(page: Page): Promise<void> {
  await field(page, "Nombre o razón social").fill(NAME);
  await field(page, "NIF").fill(NIF);
  await field(page, "Domicilio fiscal").fill(ADDRESS);
}

/** La fila (tabla) o la tarjeta (móvil) de una serie: las dos vistas están en el DOM y solo una se ve. */
const seriesRow = (page: Page, code: string): Locator =>
  shown(page.locator("article, tbody tr")).filter({ has: page.locator(`h3:text-is("Serie ${code}"), th:text-is("${code}")`) });
const randomCode = (): string => `E${randomUUID().slice(0, 6).toUpperCase()}`;

async function openAddSeries(page: Page): Promise<void> {
  if (!(await page.locator("#serie-nueva-code").isVisible())) await page.locator("summary", { hasText: "Añadir serie" }).click();
  await expect(page.locator("#serie-nueva-code")).toBeVisible();
}

async function addSeries(page: Page, code: string, first?: string): Promise<void> {
  await openAddSeries(page);
  await page.locator("#serie-nueva-code").fill(code.toLowerCase());
  await page.locator("#serie-nueva-first_number").fill(first ?? "");
  await page.getByRole("button", { name: "Añadir serie" }).click();
}

// --- AC-01 · AC-02 ----------------------------------------------------------------------------------------------------------------

test("perfil vacío (AC-01): Inicio dice qué falta, por nombre, y /perfil también", async ({ gastosPage: page, profile }) => {
  void profile;
  await settle(page);
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { level: 2, name: "Completa tu perfil" })).toBeVisible();
  const notice = page.getByRole("region", { name: "Completa tu perfil" });
  for (const label of ["Nombre o razón social", "NIF", "Domicilio fiscal"]) await expect(notice.getByRole("listitem").filter({ hasText: label })).toBeVisible();
  await expect(notice.getByRole("link", { name: "Ir a mi perfil" })).toHaveAttribute("href", "/perfil");

  await openPerfil(page);
  await expect(state(page, "Para emitir facturas te falta: Nombre o razón social, NIF, Domicilio fiscal.")).toBeVisible();
});

test("completar el perfil (AC-02): se guarda normalizado, el estado cambia y el aviso de Inicio desaparece", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await field(page, "Nombre o razón social").fill(NAME);
  await field(page, "NIF").fill("12345678 z"); // minúscula y con espacio
  await field(page, "Domicilio fiscal").fill(ADDRESS);
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await expect(field(page, "NIF")).toHaveValue(NIF);
  await expect(state(page, "Tu perfil está listo para emitir facturas.")).toBeVisible();

  await settle(page);
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Hola");
  await expect(page.getByRole("heading", { level: 2, name: "Completa tu perfil" })).toHaveCount(0);
});

// --- AC-03 · AC-06 · AC-07 --------------------------------------------------------------------------------------------------------

test("NIF e IBAN inválidos (AC-03, AC-06): un error junto a cada campo, el resumen recibe el foco y no se guarda nada", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await fillValid(page);
  await field(page, "NIF").fill("12345678A"); // letra de control equivocada
  await field(page, "IBAN").fill("ES91 2100 0418 4502 0005 1333"); // dígito de control mal
  await save(page).click();

  await expect(summary(page)).toBeVisible();
  await expect(summary(page)).toBeFocused();
  await expect(error(page, "tax_id")).toContainText("El NIF no es válido");
  await expect(error(page, "iban")).toContainText("El IBAN no es válido");
  await expect(field(page, "NIF")).toHaveAttribute("aria-invalid", "true");
  await expect(field(page, "NIF")).toHaveAttribute("aria-describedby", /perfil-tax_id-error/);
  await expect(summary(page)).not.toContainText("12345678A");
  await expect(summary(page)).not.toContainText("1333");

  await openPerfil(page); // nada se guardó, ni el nombre, que era válido
  await expect(field(page, "Nombre o razón social")).toHaveValue("");
  await expect(field(page, "NIF")).toHaveValue("");
});

test("un NIF-IVA de la UE no es un NIF español (AC-03)", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await fillValid(page);
  await field(page, "NIF").fill("FR40303265045");
  await save(page).click();
  await expect(error(page, "tax_id")).toContainText("Escribe un NIF, NIE o CIF español.");
});

test("IBAN y vivienda (AC-06, AC-07): el IBAN se guarda normalizado y se muestra agrupado; 100,01 se rechaza junto a su campo", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await fillValid(page);
  await field(page, "IBAN").fill("es91 2100 0418 4502 0005 1332");
  await field(page, "Vivienda afecta a la actividad (%)").fill("100.01");
  await save(page).click();
  await expect(error(page, "home_pct")).toContainText("Escribe un porcentaje entre 0 y 100");

  await field(page, "Vivienda afecta a la actividad (%)").fill("30");
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await expect(field(page, "IBAN")).toHaveValue(IBAN);
  await expect(field(page, "Vivienda afecta a la actividad (%)")).toHaveValue("30.00");
});

// --- AC-04 · AC-05 ----------------------------------------------------------------------------------------------------------------

test("retención (AC-04, AC-05): sugiere y avisa según la fecha de alta, sin imponer nada", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await fillValid(page);
  await field(page, "Fecha de alta").fill(`${YEAR}-01-15`);
  await field(page, "Retención de IRPF").selectOption("7.00");
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await expect(text(page, `el 7 % vale hasta el ${YEAR + 2}`)).toBeVisible();
  await expect(text(page, /Aviso \(orientativo\)/)).toHaveCount(0);

  await field(page, "Fecha de alta").fill("2020-01-15");
  await save(page).click();
  await expect(text(page, /Aviso \(orientativo\): El 7 % solo se aplica el año del alta y los dos siguientes/)).toBeVisible();
  await expect(text(page, "Sugerencia según tu fecha de alta: 15 %")).toBeVisible();

  await field(page, "Retención de IRPF").selectOption("15.00"); // elegir 15 % nunca avisa
  await save(page).click();
  await expect(text(page, /Aviso \(orientativo\)/)).toHaveCount(0);
  await expect(field(page, "Retención de IRPF")).toHaveValue("15.00");
});

// --- AC-14 · AC-15 · AC-16 --------------------------------------------------------------------------------------------------------

test("logo (AC-14, AC-15, AC-16): se rechaza lo que no vale antes de subir; se sube directo, se ve, se sustituye y se quita", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  const input = page.locator("#perfil-logo");

  await input.setInputFiles({ name: "logo.svg", mimeType: "image/svg+xml", buffer: Buffer.from("<svg xmlns='http://www.w3.org/2000/svg'/>") });
  await expect(text(page, "El logo tiene que ser una imagen PNG, JPEG o WebP.")).toBeVisible();
  await input.setInputFiles({ name: "grande.png", mimeType: "image/png", buffer: Buffer.alloc(1_048_577) });
  await expect(text(page, "El logo no puede pesar más de 1 MiB.")).toBeVisible();
  await expect(page.getByRole("img", { name: "Logo de tu negocio" })).toHaveCount(0);

  await input.setInputFiles(pngFile("logo.png", "fixture:logo"));
  await expect(text(page, "Logo guardado.")).toBeVisible({ timeout: 20_000 });
  const logo = page.getByRole("img", { name: "Logo de tu negocio" });
  await expect(logo).toBeVisible();
  await expect.poll(() => logo.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);

  await input.setInputFiles(pngFile("otro.png", "fixture:logo")); // sustituirlo: sigue habiendo un solo logo
  await expect(text(page, "Logo guardado.")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("img", { name: "Logo de tu negocio" })).toHaveCount(1);

  await page.getByRole("button", { name: "Quitar logo" }).click();
  await expect(text(page, "Logo quitado.")).toBeVisible();
  await expect(page.getByRole("img", { name: "Logo de tu negocio" })).toHaveCount(0);
  await expect(text(page, "Sin logo")).toBeVisible();
});

// --- AC-09 a AC-13 ----------------------------------------------------------------------------------------------------------------

test("series (AC-09 a AC-13): la del año aparece sola; añadir, repetir, predeterminar, archivar, reactivar y editar", async ({ gastosPage: page, profile }) => {
  await profile.save(VALID); // crea la serie del año
  await openPerfil(page);
  const year = seriesRow(page, String(YEAR));
  await expect(year).toHaveCount(1);
  await expect(year).toContainText("Predeterminada");
  await expect(year).toContainText("Serie del año");

  const code = randomCode();
  await addSeries(page, code, "100");
  await expect(text(page, "Serie añadida.")).toBeVisible();
  await expect(seriesRow(page, code)).toContainText("100"); // el siguiente número
  await expect(seriesRow(page, code)).not.toContainText("Predeterminada");

  await addSeries(page, code); // repetida
  await expect(shown(page.locator("#serie-nueva-code-error"))).toContainText("Ya tienes una serie con ese código");

  await seriesRow(page, code).getByRole("button", { name: `Hacer predeterminada la serie ${code}` }).click();
  await expect(text(page, "Serie predeterminada cambiada.")).toBeVisible();
  await expect(seriesRow(page, code)).toContainText("Predeterminada");
  await expect(seriesRow(page, String(YEAR))).not.toContainText("Predeterminada");

  await seriesRow(page, code).getByRole("button", { name: `Archivar la serie ${code}` }).click(); // la predeterminada no se archiva
  await expect(text(page, "Elige otra serie como predeterminada antes de archivar esta.")).toBeVisible();

  await seriesRow(page, String(YEAR)).getByRole("button", { name: `Hacer predeterminada la serie ${YEAR}` }).click();
  await expect(seriesRow(page, String(YEAR))).toContainText("Predeterminada");
  await seriesRow(page, code).getByRole("button", { name: `Archivar la serie ${code}` }).click();
  await expect(seriesRow(page, code)).toContainText("Archivada");
  await seriesRow(page, code).getByRole("button", { name: `Reactivar la serie ${code}` }).click();
  await expect(seriesRow(page, code)).not.toContainText("Archivada");

  await seriesRow(page, code).getByRole("button", { name: `Editar la serie ${code}` }).click();
  await seriesRow(page, code).getByLabel("Descripción").fill("Facturas rectificativas"); // el editor vive dentro de su fila o tarjeta
  await seriesRow(page, code).getByRole("button", { name: "Guardar serie" }).click();
  await expect(text(page, "Serie guardada.")).toBeVisible();
  await expect(seriesRow(page, code)).toContainText("Facturas rectificativas");
});

test("series: un código inválido sale junto a su campo y no se crea nada (AC-10)", async ({ gastosPage: page, profile }) => {
  await profile.save(VALID);
  await openPerfil(page);
  const before = await shown(page.locator("article, tbody tr")).count();
  await addSeries(page, "AB CD");
  await expect(shown(page.locator("#serie-nueva-code-error"))).toContainText("El código de la serie lleva de 1 a 8 letras, números o guiones");
  await expect(summary(page)).toBeFocused();
  await expect(shown(page.locator("article, tbody tr"))).toHaveCount(before); // no se creó ninguna
});

// --- AC-18 ------------------------------------------------------------------------------------------------------------------------

test("el NIF del perfil y los gastos (AC-18): el enlace «Completa tu perfil» de una simplificada y el aviso de destinatario", async ({ gastosPage: page, profile }) => {
  // Una simplificada sin el NIF de la persona en el perfil: la revisión lo dice y enlaza a /perfil.
  await uploadAndOpen(page, pdfFile(uniqueName("simplificada", "pdf"), "fixture:ticket_simplified"));
  const review = page.url();
  const checks = page.getByRole("region", { name: "Comprobaciones" });
  const link = checks.getByRole("link", { name: "Completa tu perfil" });
  await expect(link).toBeVisible();
  await expect(checks).toContainText("Para deducir el IVA de un ticket o una simplificada tu NIF tiene que estar en el perfil");

  await link.click();
  await expect(page).toHaveURL(/\/perfil$/);
  await fillValid(page);
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await settle(page);
  await page.goto(review);
  await expect(page.getByRole("region", { name: "Comprobaciones" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Comprobaciones" }).getByRole("link", { name: "Completa tu perfil" })).toHaveCount(0);

  // Una factura completa a un destinatario: sin NIF en el perfil no hay aviso; con otro, aparece; con el suyo, no.
  await profile.save({}); // vuelve a vacío
  await uploadAndOpen(page, pdfFile(uniqueName("completa", "pdf"), "fixture:invoice_ok"));
  const invoice = page.url();
  const panel = (): Locator => page.getByRole("region", { name: "Comprobaciones" });
  await expect(panel()).toBeVisible();
  await expect(panel()).not.toContainText(MISMATCH);

  await profile.save({ ...VALID, tax_id: OTHER_NIF });
  await settle(page);
  await page.goto(invoice);
  await expect(panel()).toContainText(MISMATCH);

  await profile.save(VALID);
  await settle(page);
  await page.goto(invoice);
  await expect(panel()).toBeVisible();
  await expect(panel()).not.toContainText(MISMATCH);
});

// --- AC-19 ------------------------------------------------------------------------------------------------------------------------

test("interfaz (AC-19): sin scroll horizontal, campos etiquetados, tarjetas o tabla según el ancho y sin errores de consola", async ({ gastosPage: page, profile }, testInfo) => {
  await profile.save(VALID);
  await openPerfil(page);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
  const wide = testInfo.project.use.viewport!.width >= 1280;
  await expect(page.getByRole("table", { name: /Series de facturación/ })).toHaveCount(wide ? 1 : 0);
  await openAddSeries(page);
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
});

test("interfaz (AC-19): la tabla de series aparece desde 1.280 px y las tarjetas hasta 1.279, sin scroll horizontal", async ({ gastosPage: page, profile, browserName }) => {
  test.skip(browserName !== "chromium", "el ancho límite es el mismo en todos los motores: se comprueba en uno");
  await profile.save(VALID);
  await openPerfil(page);
  for (const [width, table] of [
    [1279, false],
    [1280, true],
  ] as const) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("table", { name: /Series de facturación/ })).toHaveCount(table ? 1 : 0);
    await expectNoHorizontalScroll(page);
  }
});

test("interfaz (AC-19): con el teclado se llega a todos los campos hasta «Guardar» y el foco se ve", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  const first = field(page, "Nombre o razón social");
  const signature = (locator: Locator) =>
    locator.evaluate((el) => {
      const style = getComputedStyle(el);
      return [style.boxShadow, style.outlineStyle, style.outlineWidth, style.outlineColor, style.borderColor].join("|");
    });
  const resting = await signature(first);
  await first.focus();
  expect(await signature(first), "el campo no muestra el foco").not.toBe(resting);

  const visited: string[] = [];
  for (let presses = 0; presses < 20; presses++) {
    visited.push(await page.evaluate(() => document.activeElement?.id ?? ""));
    if (await save(page).evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(save(page)).toBeFocused();
  for (const id of ["perfil-legal_name", "perfil-tax_id", "perfil-fiscal_address", "perfil-activity", "perfil-iae_epigraph", "perfil-activity_start_date", "perfil-irpf_rate", "perfil-home_pct", "perfil-iban"]) {
    expect(visited, `el foco no pasó por ${id}`).toContain(id);
  }
});
