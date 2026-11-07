// SPEC-W-003 · Registrar el gasto: comprobaciones, categoría, gasto sin factura, gastos registrados y anulación, en los seis proyectos
// (Chromium, Firefox y WebKit; 390 y 1.440 px). AC-01, 02, 08, 09, 10, 11, 12, 13, 14 y 18 en un navegador de verdad.
//
// Igual que `gastos-subida.spec.ts`: la API lee con `HttpAgentsClient` contra el servidor de agentes de E2E y cada prueba elige qué lee con el
// marcador `fixture:<nombre>` del archivo que sube. Cada worker usa una cuenta de `usuario` nueva (`gastosUser`) que **comparten sus
// pruebas**, y varias registran la misma factura de ejemplo: por eso el fixture `ledger` anula al terminar todo gasto vivo de la cuenta (y
// aquí también al empezar). La interfaz no valida nada fiscal: estas pruebas comprueban que enseña lo que calcula el servidor.
import type { Locator, Page } from "@playwright/test";

import { expect, settle, test } from "./helpers/fixtures";
import { pdfFile, pngFile, uniqueName, type UploadFile } from "./helpers/files";
import {
  DOCUMENT_URL,
  card,
  field,
  idFrom,
  openGastos,
  registerButton,
  savedMessage,
  settleForm,
  shown,
  text,
  upload,
  uploadAndOpen,
} from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";
import { SEEDED_CONCEPT, seededConcept } from "./helpers/ledger";

const EXPENSE_URL = /\/gastos\/registrados\/[0-9a-f-]{36}$/;

// Empezar sin gastos vivos (y, al terminar, el fixture `ledger` los anula): ninguna prueba depende de lo que dejó otra.
test.beforeEach(async ({ ledger }) => {
  await ledger.voidAll();
});

/** El panel «Comprobaciones» de la pantalla de revisión. */
const checks = (page: Page): Locator => page.getByRole("region", { name: "Comprobaciones" });
const checkRow = (page: Page, label: string): Locator => checks(page).getByRole("listitem").filter({ hasText: label });
/** La sección «Gastos registrados» de /gastos. */
const registered = (page: Page): Locator => page.getByRole("region", { name: "Gastos registrados" });
/** La fila (tabla) o la tarjeta (móvil) de un gasto registrado: las dos vistas están en el DOM y solo una se ve. */
const rowOf = (page: Page, name: string | RegExp): Locator => shown(registered(page).locator("tbody tr, article")).filter({ hasText: name });
const notice = (page: Page, message: string): Locator => page.getByRole("status").filter({ hasText: message });
/** El motivo, junto al botón, de que «Registrar gasto» no se pueda pulsar. */
const reason = (page: Page): Locator => shown(page.locator("#registrar-motivo"));

/** Abre la revisión de un documento ya subido desde la lista de documentos (su tarjeta enlaza por el proveedor, o por el nombre del archivo si aún no se leyó). */
async function openDocument(page: Page, file: UploadFile): Promise<string> {
  await openGastos(page);
  await card(page, file).getByRole("link").click();
  await expect(page).toHaveURL(DOCUMENT_URL);
  await expect(page.getByRole("heading", { level: 1, name: file.name })).toBeVisible();
  return idFrom(page);
}

/** Pulsa «Registrar gasto» y espera a volver a /gastos con el aviso. */
async function register(page: Page): Promise<void> {
  await registerButton(page).click();
  await expect(page).toHaveURL(/\/gastos\?aviso=registrado$/);
  await expect(notice(page, "Gasto registrado.")).toBeVisible();
}

/** Abre el detalle de un gasto registrado por su fila (o tarjeta) y devuelve su identificador. */
async function openExpense(page: Page, name: string): Promise<string> {
  await rowOf(page, name).getByRole("link", { name }).click();
  await expect(page).toHaveURL(EXPENSE_URL);
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  return idFrom(page);
}

/** Cuenta los cuadros de diálogo del navegador (`confirm`, `alert`…): anular y descartar no deben abrir ninguno. */
function countDialogs(page: Page): { count: () => number } {
  let seen = 0;
  page.on("dialog", (dialog) => {
    seen += 1;
    void dialog.dismiss();
  });
  return { count: () => seen };
}

test("registrar una factura (AC-02, AC-12, AC-18): las comprobaciones salen del servidor, la categoría sugerida está marcada y el gasto aparece en la lista", async ({
  gastosPage: page,
}) => {
  const file = pdfFile(uniqueName("factura-nubesoft", "pdf"), "fixture:invoice_ok"); // un PDF, para ver el original en su <iframe>
  const documentId = await uploadAndOpen(page, file);

  // Cada comprobación lleva icono y texto (no solo color) y todas están correctas.
  const panel = checks(page);
  await expect(panel).toBeVisible();
  const rows = panel.getByRole("listitem");
  const total = await rows.count();
  expect(total).toBeGreaterThanOrEqual(8);
  await expect(rows.locator("svg")).toHaveCount(total);
  await expect(panel.getByText("revisar", { exact: true })).toHaveCount(0);
  await expect(checkRow(page, "No está registrada ya")).toContainText("Correcta");
  await expect(checkRow(page, "Base más IVA igual al total")).toContainText("Correcta");

  // El IVA se deduce (factura completa de un proveedor español) y la categoría sugerida sale marcada; sin sospecha no hay casilla.
  await expect(panel.getByText("Se deducirá el IVA: sí.")).toBeVisible();
  const category = panel.getByLabel("Categoría");
  await expect(category).toHaveValue("software");
  await expect(category.locator("option:checked")).toHaveText("Software · sugerida");
  await expect(panel.getByRole("checkbox")).toHaveCount(0);
  await expect(registerButton(page)).toBeEnabled();
  await expect(reason(page)).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  await register(page);
  const row = rowOf(page, "Nubesoft S.L.");
  await expect(row).toContainText("28/10/2026");
  await expect(row).toContainText("Software");
  await expect(row).toContainText(/30,00\s€/);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // Mientras el gasto cuenta, la pantalla de revisión del documento lleva a su gasto.
  await settle(page);
  await page.goto(`/gastos/${documentId}`);
  await expect(page).toHaveURL(EXPENSE_URL);
  await expect(page.getByRole("heading", { level: 1, name: "Nubesoft S.L." })).toBeVisible();
  const table = page.getByRole("table", { name: "Desglose de IVA" });
  await expect(table).toBeVisible();
  await expect(table).toContainText(/24,79\s€/);
  await expect(table).toContainText(/5,21\s€/);
  await expect(text(page, "IVA deducible: sí.")).toBeVisible();
  await expect(shown(page.locator('iframe[title^="Documento original"]'))).toHaveAttribute("src", `/gastos/${documentId}/original`);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // Cambiar la categoría (AC-12): el botón solo se activa si cambia, y la lista lo refleja.
  const change = page.getByRole("button", { name: "Cambiar categoría" });
  await expect(change).toBeDisabled();
  await field(page, "Categoría").selectOption("advisory");
  await expect(change).toBeEnabled();
  await change.click();
  await expect(notice(page, "Categoría actualizada.")).toBeVisible();
  await openGastos(page);
  await expect(rowOf(page, "Nubesoft S.L.")).toContainText("Asesoría");
});

test("suma que no cuadra (AC-01): la comprobación fallida dice por qué y «Registrar gasto» no se activa ni guardando", async ({ gastosPage: page }) => {
  const file = pngFile(uniqueName("factura-imprenta", "png"), "fixture:invoice_sum_mismatch");
  await uploadAndOpen(page, file);

  const sum = checkRow(page, "Base más IVA igual al total");
  await expect(sum).toContainText("revisar");
  await expect(sum).toContainText(/Base más IVA da 145,20\s€ y el total indicado es 147,00\s€\./);
  await expect(sum.locator("svg")).toHaveCount(1); // icono además del texto
  await expect(checkRow(page, "Datos dudosos revisados")).toContainText("revisar"); // la lectura dudó del total y nadie lo ha revisado
  await expect(registerButton(page)).toBeDisabled();
  await expect(reason(page)).toHaveText("Corrige las comprobaciones marcadas y guarda los cambios.");

  // Guardar sin cambios confirma el dato dudoso, pero la suma sigue sin cuadrar: el servidor no deja registrarla.
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(savedMessage(page)).toBeVisible();
  await expect(checkRow(page, "Datos dudosos revisados")).toContainText("Correcta");
  await expect(sum).toContainText("revisar");
  await expect(registerButton(page)).toBeDisabled();
  await expect(reason(page)).toHaveText("Corrige las comprobaciones marcadas y guarda los cambios.");
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // No se ha registrado nada.
  await openGastos(page);
  await expect(registered(page)).toContainText("Todavía no hay gastos registrados.");
});

test("dato dudoso (AC-10): sin guardar no se registra; al guardar el dato corregido, las comprobaciones se rehacen y sí", async ({ gastosPage: page }) => {
  const file = pngFile(uniqueName("ticket-dudoso", "png"), "fixture:invoice_doubtful_nif");
  await uploadAndOpen(page, file);

  await expect(checkRow(page, "NIF del proveedor válido")).toContainText("revisar");
  await expect(registerButton(page)).toBeDisabled();

  // Un cambio sin guardar: el panel lo dice y el botón sigue sin poder pulsarse, aunque lo escrito sea correcto.
  await field(page, "NIF del proveedor").fill("B00000075");
  await expect(reason(page)).toHaveText("Guarda los cambios para volver a comprobar.");
  await expect(text(page, "Comprobado con lo último que guardaste.")).toBeVisible();
  await expect(registerButton(page)).toBeDisabled();

  // Guardado, el servidor comprueba lo nuevo (y el dato dudoso queda revisado): todo en verde y el botón se activa.
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(savedMessage(page)).toBeVisible();
  await expect(checkRow(page, "NIF del proveedor válido")).toContainText("Correcta");
  await expect(checkRow(page, "Datos dudosos revisados")).toContainText("Correcta");
  await expect(registerButton(page)).toBeEnabled();
  await expect(reason(page)).toHaveCount(0);

  await register(page);
  await expect(rowOf(page, "Imprenta Sol S.L.")).toContainText(/145,20\s€/);
});

test("instrucciones ocultas (AC-09, AC-18): la casilla solo sale con sospecha, hace falta marcarla y el detalle deja constancia", async ({
  gastosPage: page,
}) => {
  const file = pngFile(uniqueName("factura-aurora", "png"), "fixture:invoice_injection");
  await uploadAndOpen(page, file);

  // La sospecha no cambia ninguna comprobación: todas en verde, y aun así el botón espera a la casilla.
  const panel = checks(page);
  await expect(panel.getByText("revisar", { exact: true })).toHaveCount(0);
  const acknowledge = panel.getByRole("checkbox", { name: "He comparado los datos con el original." });
  await expect(acknowledge).not.toBeChecked();
  await expect(registerButton(page)).toBeDisabled();
  await expect(reason(page)).toHaveText("Marca que has comparado los datos con el original.");

  await acknowledge.check();
  await expect(registerButton(page)).toBeEnabled();
  await expect(reason(page)).toHaveCount(0);
  await acknowledge.uncheck();
  await expect(registerButton(page)).toBeDisabled();
  await acknowledge.check();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  await register(page);
  await openExpense(page, "Servicios Aurora S.L.");
  await expect(text(page, /Se registró después de confirmar que se compararon los datos con el original/)).toBeVisible();
});

test("la misma factura dos veces (AC-08): la segunda no se registra mientras la primera cuente, y sí al anularla", async ({ gastosPage: page }) => {
  const first = pngFile(uniqueName("nubesoft-a", "png"), "fixture:invoice_ok");
  const second = pngFile(uniqueName("nubesoft-b", "png"), "fixture:invoice_ok");
  await openGastos(page);
  await upload(page, first, second);

  const firstId = await openDocument(page, first);
  await register(page);

  // La misma factura (mismo NIF y número) en otro documento: la comprobación falla con su motivo y no se puede registrar.
  await openDocument(page, second);
  const duplicate = checkRow(page, "No está registrada ya");
  await expect(duplicate).toContainText("revisar");
  await expect(duplicate).toContainText("Ya hay un gasto registrado con el mismo NIF del proveedor y el mismo número de factura.");
  await expect(registerButton(page)).toBeDisabled();
  await expect(reason(page)).toHaveText("Corrige las comprobaciones marcadas y guarda los cambios.");

  // Anular la primera la libera: su documento vuelve a «Para revisar» y la segunda ya se puede registrar.
  await openGastos(page);
  await openExpense(page, "Nubesoft S.L.");
  await page.getByRole("button", { name: "Anular gasto" }).click();
  await page.getByRole("button", { name: "Sí, anular" }).click();
  await expect(page).toHaveURL(`/gastos/${firstId}?aviso=anulado-documento`);
  await openDocument(page, second);
  await expect(checkRow(page, "No está registrada ya")).toContainText("Correcta");
  await expect(registerButton(page)).toBeEnabled();
  await register(page);
  await expect(rowOf(page, "Nubesoft S.L.")).toHaveCount(1);

  // Y ahora la primera, de vuelta en revisión, es la repetida.
  await openDocument(page, first);
  await expect(checkRow(page, "No está registrada ya")).toContainText("revisar");
  await expect(registerButton(page)).toBeDisabled();
});

test("la misma factura dos veces (AC-08), ticket: con otro número ya no es un duplicado, solo un aviso que no bloquea", async ({ gastosPage: page }) => {
  const first = pngFile(uniqueName("ticket-a", "png"), "fixture:ticket_simplified");
  const second = pngFile(uniqueName("ticket-b", "png"), "fixture:ticket_simplified");
  await uploadAndOpen(page, first);

  // Una factura simplificada sin el NIF de la persona no deduce el IVA, y el servidor dice por qué.
  await expect(checks(page).getByText("Se deducirá el IVA: no.")).toBeVisible();
  await expect(checks(page)).toContainText("Factura simplificada: el IVA solo se deduce si lleva tu NIF.");
  await register(page);
  await expect(rowOf(page, "Papelería Arce S.L.")).toContainText("IVA no deducible");

  // El mismo ticket (mismo NIF y número) es un duplicado.
  await uploadAndOpen(page, second);
  await expect(checkRow(page, "No está registrada ya")).toContainText("revisar");
  await expect(registerButton(page)).toBeDisabled();

  // Con otro número, mismo proveedor, día e importe: queda el aviso («comprueba que no es el mismo») y se puede registrar.
  await field(page, "Número de factura").fill("T-58214");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(savedMessage(page)).toBeVisible();
  await expect(checkRow(page, "No está registrada ya")).toContainText("Correcta");
  await expect(text(page, "Ya hay un gasto con el mismo proveedor, día e importe: comprueba que no es el mismo.")).toBeVisible();
  await expect(registerButton(page)).toBeEnabled();
  await register(page);
  await expect(rowOf(page, "Papelería Arce S.L.")).toHaveCount(2);
});

test("gasto sin factura (AC-11, AC-18): cada error sale junto a su campo y, bien rellenado, se anota y se puede anular", async ({ gastosPage: page }) => {
  const dialogs = countDialogs(page);
  await openGastos(page);
  await page.getByRole("link", { name: "Añadir gasto sin factura" }).click();
  await expect(page).toHaveURL(/\/gastos\/nuevo$/);
  await expect(page.getByRole("heading", { level: 1, name: "Gasto sin factura" })).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // Vacío: el resumen recibe el foco y cada error está junto a su campo, enlazado con `aria-describedby`.
  const save = page.getByRole("button", { name: "Guardar gasto" });
  await save.click();
  const summary = page.getByRole("alert").filter({ hasText: "Revisa estos datos" });
  await expect(summary).toBeVisible();
  await expect(summary).toBeFocused();
  await expect(shown(page.locator("#gasto-concept-error"))).toHaveText("Describe el gasto, por ejemplo «Cuota de autónomos».");
  await expect(shown(page.locator("#gasto-amount-error"))).toHaveText("Escribe el importe del gasto.");
  await expect(field(page, "Concepto")).toHaveAttribute("aria-invalid", "true");
  await expect(field(page, "Concepto")).toHaveAttribute("aria-describedby", /gasto-concept-error/);
  await expectNoHorizontalScroll(page);
  await settleForm(page); // tras cada envío fallido, antes de escribir de nuevo (ver `settleForm`)

  // Un importe ambiguo no se envía ni se adivina; lo ya escrito se conserva.
  await field(page, "Concepto").fill("Cuota de autónomos");
  await field(page, "Importe (€)").fill("1.200");
  await save.click();
  await expect(shown(page.locator("#gasto-amount-error"))).toHaveText("No entendemos este importe. Escríbelo así: 1.234,50");
  await expect(field(page, "Concepto")).toHaveValue("Cuota de autónomos");
  await settleForm(page);

  // La fecha futura la decide la API (con el «hoy» de Madrid) y su mensaje sale junto al campo.
  await field(page, "Importe (€)").fill("294,00");
  await field(page, "Fecha").fill("2099-12-31");
  await save.click();
  await expect(shown(page.locator("#gasto-expense_date-error"))).toHaveText("La fecha no puede ser futura ni anterior al 1 de enero de 2000.");
  await expect(page).toHaveURL(/\/gastos\/nuevo$/);
  await settleForm(page);

  // Bien rellenado: se anota sin IVA y aparece en la lista con su marca.
  await field(page, "Fecha").fill("2026-11-01");
  await save.click();
  await expect(page).toHaveURL(/\/gastos\?aviso=anotado$/);
  await expect(notice(page, "Gasto anotado.")).toBeVisible();
  const row = rowOf(page, "Cuota de autónomos");
  await expect(row).toContainText("Sin factura");
  await expect(row).toContainText("01/11/2026");
  await expect(row).toContainText(/294,00\s€/);
  await expect(rowOf(page, /./)).toHaveCount(1); // lo rechazado antes no creó nada
  await expectNoHorizontalScroll(page);

  // Detalle: sin factura no hay IVA ni original. Anular es en dos pasos y sin cuadros de diálogo del navegador.
  await openExpense(page, "Cuota de autónomos");
  await expect(text(page, "IVA deducible: no hay IVA que deducir.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Desglose de IVA" })).toHaveCount(0);
  await expect(shown(page.locator('iframe[title^="Documento original"]'))).toHaveCount(0);
  await page.getByRole("button", { name: "Anular gasto" }).click();
  const question = page.getByRole("group", { name: /¿Anular este gasto\?/ });
  await expect(question).toContainText("no se puede recuperar");
  await question.getByRole("button", { name: "Sí, anular" }).click();
  await expect(page).toHaveURL(/\/gastos\?aviso=anulado$/);
  await expect(notice(page, "Gasto anulado.")).toBeVisible();
  await expect(rowOf(page, "Cuota de autónomos")).toHaveCount(0);
  expect(dialogs.count(), "el navegador abrió un cuadro de diálogo").toBe(0);
});

test("anular y volver a registrar (AC-13): el documento vuelve a «Para revisar», el segundo registro es un gasto nuevo y el anulado ya no admite cambios", async ({
  gastosPage: page,
}) => {
  const dialogs = countDialogs(page);
  const file = pngFile(uniqueName("factura-nubesoft", "png"), "fixture:invoice_ok");
  const documentId = await uploadAndOpen(page, file);
  await register(page);
  const firstExpense = await openExpense(page, "Nubesoft S.L.");

  // Anular: la pregunta dice qué pasa con el documento y la opción segura tiene el foco.
  await page.getByRole("button", { name: "Anular gasto" }).click();
  const question = page.getByRole("group", { name: /¿Anular este gasto\?/ });
  await expect(question).toContainText("el documento vuelve a «Para revisar»");
  await expect(question.getByRole("button", { name: "Cancelar" })).toBeFocused();
  await question.getByRole("button", { name: "Sí, anular" }).click();
  await expect(page).toHaveURL(`/gastos/${documentId}?aviso=anulado-documento`);
  await expect(notice(page, "Gasto anulado: el documento vuelve a «Para revisar».")).toBeVisible();
  await expect(text(page, "Para revisar").first()).toBeVisible();
  await expect(field(page, "Proveedor")).toHaveValue("Nubesoft S.L."); // su lectura y su revisión siguen ahí

  // El gasto anulado no cuenta: no sale en la lista.
  await openGastos(page);
  await expect(rowOf(page, "Nubesoft S.L.")).toHaveCount(0);

  // Registrar de nuevo es un gasto nuevo.
  await openDocument(page, file);
  await expect(registerButton(page)).toBeEnabled();
  await register(page);
  const secondExpense = await openExpense(page, "Nubesoft S.L.");
  expect(secondExpense).not.toBe(firstExpense);

  // El primero sigue consultable, marcado como anulado y sin acciones.
  await settle(page);
  await page.goto(`/gastos/registrados/${firstExpense}`);
  await expect(page.getByRole("status").filter({ hasText: "Este gasto está anulado." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Anular gasto" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cambiar categoría" })).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  expect(dialogs.count(), "el navegador abrió un cuadro de diálogo").toBe(0);
});

test("lista paginada (AC-14, AC-18): «Ver más antiguos» sigue la lista, un cursor manipulado vuelve al principio y a 1.280 px las tarjetas pasan a tabla", async ({
  gastosPage: page,
  ledger,
}) => {
  await ledger.seed(51);
  await openGastos(page);
  const list = registered(page);

  // Primera página: 50 gastos, del más reciente al más antiguo, y un enlace a los anteriores.
  await expect(rowOf(page, SEEDED_CONCEPT)).toHaveCount(50);
  await expect(rowOf(page, seededConcept(51))).toBeVisible();
  await expect(rowOf(page, seededConcept(2))).toBeVisible();
  await expect(rowOf(page, seededConcept(1))).toHaveCount(0);
  await expect(list.getByRole("link", { name: "Volver a los más recientes" })).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  // Tarjetas hasta 1.279 px y tabla desde 1.280: nunca las dos a la vez y nunca con scroll horizontal.
  const original = page.viewportSize();
  expect(original).not.toBeNull();
  for (const { width, asTable } of [
    { width: 1279, asTable: false },
    { width: 1280, asTable: true },
  ]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(list.getByRole("table")).toHaveCount(asTable ? 1 : 0);
    await expect(list.getByRole("article")).toHaveCount(asTable ? 0 : 50);
    await expectNoHorizontalScroll(page);
  }
  if (original) await page.setViewportSize(original);

  // Los anteriores: el gasto que falta, sin repetir ninguno, y ya no hay más.
  await list.getByRole("link", { name: "Ver más antiguos" }).click();
  await expect(page).toHaveURL(/\/gastos\?cursor=[A-Za-z0-9_-]+$/);
  await expect(rowOf(page, SEEDED_CONCEPT)).toHaveCount(1);
  await expect(rowOf(page, seededConcept(1))).toBeVisible();
  await expect(list.getByRole("link", { name: "Ver más antiguos" })).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await list.getByRole("link", { name: "Volver a los más recientes" }).click();
  await expect(page).toHaveURL(/\/gastos$/);
  await expect(rowOf(page, SEEDED_CONCEPT)).toHaveCount(50);

  // Un cursor inventado no enseña ningún error: la API lo rechaza y se vuelve a la primera página.
  await settle(page);
  await page.goto("/gastos?cursor=cursor-inventado");
  await expect(page).toHaveURL(/\/gastos$/);
  await expect(rowOf(page, SEEDED_CONCEPT)).toHaveCount(50);
});
