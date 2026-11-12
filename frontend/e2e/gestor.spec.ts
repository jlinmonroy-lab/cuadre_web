// SPEC-W-010 · El acceso del gestor de punta a punta: «Mi gestor» del autónomo (AC-19), la cartera y la ficha de solo consulta del gestor (AC-20), los roles
// (AC-21) y el aspecto en los tres motores y a 390 y 1.440 px (AC-22).
//
// Reglas heredadas: cada prueba trabaja con la cuenta de su worker (`gastosUser`, con un NOMBRE ÚNICO) y ninguna espera cifras absolutas ni cuenta filas (RES-03);
// la gestora Gina es COMPARTIDA entre workers y proyectos, así que localiza a SU autónomo por ese nombre y el fixture `gestor` revoca todo lo abierto al empezar y
// al terminar. El correo de la invitación va a la consola del servidor (sin proveedor, DEP-05): aquí se comprueba el aviso «Invitación enviada…», no un buzón.
import { randomUUID } from "node:crypto";

import { expect, type BrowserContext, type Locator, type Page } from "@playwright/test";

import { GUS, PEOPLE, SEED_PASSWORD } from "./helpers/env";
import { BILLER_PROFILE, settle, test as base, watchBrowserErrors } from "./helpers/fixtures";
import { settleForm, shown, uploadAndOpen } from "./helpers/gastos";
import { madridToday } from "./helpers/invoices";
import { pdfFile, uniqueName } from "./helpers/files";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";
import { fillLogin, uniqueEmail } from "./helpers/session";

const GINA = PEOPLE.gina.email;
const IBAN = "ES3600000000050000000001";
const closeQuietly = (context: BrowserContext) => context.close().catch(() => undefined);

// El segundo gestor, con su propia sesión por la interfaz (no tiene sesión guardada).
const test = base.extend<{ gusPage: Page }>({
  gusPage: async ({ browser }, use, testInfo) => {
    const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
    const context = await browser.newContext({ baseURL, viewport, locale, timezoneId });
    const page = await context.newPage();
    const errors = watchBrowserErrors(page);
    await page.goto("/login");
    await fillLogin(page, GUS.email, SEED_PASSWORD);
    await expect(page).toHaveURL("/cartera");
    await use(page);
    await settle(page);
    const found = errors();
    await closeQuietly(context);
    expect(found, "el navegador registró errores").toEqual([]);
  },
});

// Lo que la ficha del gestor no puede tener jamás: ninguna acción de escribir en la contabilidad del autónomo (CONF-001 a).
const FORBIDDEN = /emitir|registrar|editar|archivar|reactivar|rectificar|anular|generar pdf|marcar como cobrada|descartar/i;

async function expectReadOnly(page: Page): Promise<void> {
  const names = async (role: "button" | "link") =>
    page
      .getByRole("main")
      .getByRole(role)
      .evaluateAll((nodes, source) => nodes.map((node) => (node.textContent ?? "").trim()).filter((text) => new RegExp(source, "i").test(text)), FORBIDDEN.source);
  expect(await names("button"), "botones de escritura").toEqual([]);
  expect(await names("link"), "enlaces de escritura").toEqual([]);
}

const ficha = (ownerId: string, tab: string, extra = "") => `/cartera/${ownerId}?tab=${tab}${extra}`;
const portfolio = (page: Page): Locator => page.getByRole("region", { name: "Tu cartera" });
const ownerCard = (page: Page, name: string): Locator => portfolio(page).getByRole("article").filter({ hasText: name });
const activity = (page: Page): Locator => page.getByRole("region", { name: "Qué ha consultado tu gestor" });
const accessRow = (page: Page, email: string): Locator => page.getByRole("region", { name: "Accesos" }).getByRole("listitem").filter({ hasText: email });

async function openGestor(page: Page): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto("/gestor");
  await expect(page.getByRole("heading", { level: 1, name: "Mi gestor" })).toBeVisible();
}

/** El texto de una hoja del 303 o del 130, con los documentos de cada casilla: `textContent` es el mismo en todos los motores (`innerText` depende del <details>). */
async function sheetText(page: Page, id: "modelo-303" | "modelo-130"): Promise<string> {
  return (await page.locator(`section[aria-labelledby="${id}"]`).evaluate((node) => node.textContent ?? "")).replace(/\s+/g, " ").trim();
}

/** Sigue una descarga del gestor sin dejar que el navegador la abra: debe ser una redirección (302) a una URL firmada que sirva el archivo. */
async function downloaded(context: BrowserContext, href: string): Promise<{ location: string; body: Buffer }> {
  const redirect = await context.request.get(href, { maxRedirects: 0 });
  expect(redirect.status(), `descarga ${href.split("/").slice(-1)[0]}`).toBe(302);
  expect(redirect.headers()["cache-control"]).toBe("no-store");
  const location = redirect.headers()["location"] ?? "";
  expect(location.startsWith("http")).toBe(true);
  const file = await context.request.get(location);
  expect(file.status()).toBe(200);
  return { location, body: await file.body() };
}

// --- «Mi gestor» (AC-01 a AC-03, AC-05, AC-19) -----------------------------------------------------------------------------------------

test("Mi gestor · invitar: errores junto al campo, éxito, y revocar con confirmación y con teclado", async ({ gastosPage: page, gastosUser, gestor }) => {
  await openGestor(page);
  const field = page.getByLabel("Correo de tu gestor");
  const invite = page.getByRole("button", { name: "Invitar", exact: true });

  const fieldError = async (value: string, message: string) => {
    await field.fill(value);
    await invite.click();
    await expect(page.getByRole("alert").filter({ hasText: message })).toBeVisible();
    await expect(field).toHaveAttribute("aria-invalid", "true");
    await expect(page.locator("#gestor-email-error")).toHaveText(message);
    await expect(field).toHaveAttribute("aria-describedby", /gestor-email-error/);
    await settleForm(page); // tras cada envío fallido, antes de escribir de nuevo: React 19 reinicia el formulario un instante después (ver `settleForm`)
  };
  await fieldError("no-es-un-correo", "Escribe un correo electrónico válido.");
  await fieldError(gastosUser.email, "No puedes invitarte a ti mismo.");
  await gestor.owner.invite(GINA); // una invitación abierta: repetirla da 409
  await fieldError(GINA, "Ya hay una invitación pendiente o un acceso activo para ese correo.");

  const fresh = `e2e-gestor-${randomUUID().slice(0, 8)}@example.test`;
  await field.fill(fresh);
  await invite.click();
  await expect(page.getByText(`Invitación enviada a ${fresh}.`)).toBeVisible();
  await expect(field).toHaveValue("");
  const row = accessRow(page, fresh);
  await expect(row.getByText("Estado: Pendiente de aceptar", { exact: true })).toBeVisible();
  await expect(row.getByText(/^Caduca el \d{1,2} \S+ \d{4} · Invitado el /)).toBeVisible();

  // Revocar: pide confirmación, con teclado (foco al confirmar, «Escape» cancela y devuelve el foco) y con el ratón.
  const revoke = row.getByRole("button", { name: `Revocar el acceso de ${fresh}` });
  await revoke.focus();
  await page.keyboard.press("Enter");
  const group = row.getByRole("group", { name: /Confirmar la revocación/ });
  await expect(group).toBeVisible();
  await expect(group.getByRole("button", { name: "Sí, revocar" })).toBeFocused();
  await expect(group).toContainText("Dejará de ver tu contabilidad al instante.");
  await page.keyboard.press("Escape");
  await expect(group).toHaveCount(0);
  await expect(revoke).toBeFocused();
  await expect(row.getByText("Estado: Pendiente de aceptar", { exact: true })).toBeVisible();
  await page.keyboard.press("Enter");
  await group.getByRole("button", { name: "Cancelar" }).click();
  await expect(group).toHaveCount(0);
  await revoke.click();
  await group.getByRole("button", { name: "Sí, revocar" }).click();
  await expect(row.getByText("Estado: Revocada", { exact: true })).toBeVisible();
  await expect(row.getByRole("button", { name: /^Revocar/ })).toHaveCount(0);

  // El registro de actividad lo cuenta, con el correo del acceso.
  await expect(activity(page).getByText(`Invitaste a ${fresh}`)).toBeVisible();
  await expect(activity(page).getByText(`Revocaste el acceso de ${fresh}`)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
});

test("Mi gestor · el límite de cinco invitaciones abiertas se dice con el texto del servidor", async ({ gastosPage: page, gestor }) => {
  for (let n = 0; n < 5; n += 1) await gestor.owner.invite(`e2e-limite-${randomUUID().slice(0, 8)}@example.test`);
  await openGestor(page);
  await page.getByLabel("Correo de tu gestor").fill(uniqueEmail("sexta"));
  await page.getByRole("button", { name: "Invitar", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /Ya tienes 5 invitaciones o accesos abiertos/ })).toBeVisible();
  // La lista conserva el historial (los revocados de otras pruebas): lo que cuenta para el límite son los abiertos, que son los que se pueden revocar.
  await expect(page.getByRole("region", { name: "Accesos" }).getByRole("button", { name: /^Revocar el acceso de/ })).toHaveCount(5);
});

test("Mi gestor · el registro de actividad se pagina de 50 en 50, lo más reciente primero", async ({ gastosPage: page, gastosUser, gestor }) => {
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);
  await gestor.gina.touch(ownerId, 55); // 55 lecturas: más de una página
  await openGestor(page);
  const entries = activity(page).getByRole("listitem");
  await expect(entries).toHaveCount(50);
  await expect(entries.first()).toContainText("Tu gestor consultó tus clientes"); // lo último que hizo
  await expect(activity(page).getByRole("link", { name: "Volver a lo más reciente" })).toHaveCount(0);

  await activity(page).getByRole("link", { name: "Ver actividad anterior" }).click();
  await expect(page).toHaveURL(/\/gestor\?actividad=\d+$/);
  expect(await entries.count()).toBeGreaterThanOrEqual(1);
  expect(await entries.count()).toBeLessThanOrEqual(50);
  await expect(activity(page).getByRole("link", { name: "Volver a lo más reciente" })).toBeVisible();
  await expectNoHorizontalScroll(page);
  await activity(page).getByRole("link", { name: "Volver a lo más reciente" }).click();
  await expect(page).toHaveURL(/\/gestor$/);
  await expect(entries).toHaveCount(50);
});

// --- Aceptar, rechazar y la cartera (AC-04, AC-07, AC-20) --------------------------------------------------------------------------

test("Cartera · Gina acepta y Gus rechaza; el autónomo ve «Activo» y «Rechazada»", async ({ pageAs, gusPage, gastosPage, gastosUser, gestor }) => {
  await gestor.owner.invite(GINA);
  await gestor.owner.invite(GUS.email);

  const gina = await pageAs("gina");
  await settle(gina);
  await gina.goto("/cartera");
  const invitation = gina.getByRole("region", { name: "Invitaciones recibidas" }).getByRole("listitem").filter({ hasText: gastosUser.name });
  await expect(invitation.getByText(/^Caduca el \d{1,2} \S+ \d{4}$/)).toBeVisible();
  await invitation.getByRole("button", { name: `Aceptar la invitación de ${gastosUser.name}` }).click();
  await expect(portfolio(gina).getByRole("link", { name: gastosUser.name })).toBeVisible();
  await expect(gina.getByRole("region", { name: "Invitaciones recibidas" }).getByText(gastosUser.name)).toHaveCount(0);

  await gusPage.goto("/cartera");
  const declined = gusPage.getByRole("region", { name: "Invitaciones recibidas" }).getByRole("listitem").filter({ hasText: gastosUser.name });
  await declined.getByRole("button", { name: `Rechazar la invitación de ${gastosUser.name}` }).click();
  await expect(gusPage.getByRole("region", { name: "Invitaciones recibidas" }).getByText(gastosUser.name)).toHaveCount(0);
  await expect(portfolio(gusPage).getByText(gastosUser.name)).toHaveCount(0);

  await openGestor(gastosPage);
  await expect(accessRow(gastosPage, GINA).getByText("Estado: Activo", { exact: true })).toBeVisible();
  await expect(accessRow(gastosPage, GUS.email).getByText("Estado: Rechazada", { exact: true })).toBeVisible();
  await expect(activity(gastosPage).getByText("Tu gestor aceptó tu invitación").first()).toBeVisible();
  await expect(activity(gastosPage).getByText("Tu gestor rechazó tu invitación").first()).toBeVisible();
});

test("Cartera · los pendientes salen con su número y con palabras, y el original se descarga por URL firmada", async ({ pageAs, gastosPage, gastosUser, gestor }) => {
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);
  const before = await gestor.gina.pendingOf(gastosUser.name);

  const first = pdfFile(uniqueName("pend-uno", "pdf"), "fixture:invoice_ok");
  const second = pdfFile(uniqueName("pend-dos", "pdf"), "fixture:invoice_ok");
  await uploadAndOpen(gastosPage, first);
  await uploadAndOpen(gastosPage, second);
  const after = await gestor.gina.pendingOf(gastosUser.name);
  expect(after).toBe(before + 2);

  const gina = await pageAs("gina");
  await settle(gina);
  await gina.goto("/cartera");
  const card = ownerCard(gina, gastosUser.name);
  await expect(card.getByText(`${after} documentos para revisar`)).toBeVisible();
  await expect(card.getByText(String(after), { exact: true })).toBeVisible();

  await gina.goto(ficha(ownerId, "documentos"));
  const docs = gina.getByRole("region", { name: "Documentos para revisar" });
  await expect(docs.getByText(first.name)).toBeVisible();
  await expect(docs.getByText(second.name)).toBeVisible();
  const original = docs.getByRole("article").filter({ hasText: first.name }).getByRole("link", { name: /^Abrir el original/ });
  await expect(original).toHaveAttribute("href", /^\/cartera\/[0-9a-f-]{36}\/documentos\/[0-9a-f-]{36}\/original$/);
  await expect(docs.getByRole("link", { name: first.name })).toHaveCount(0); // sin enlace a la pantalla de revisión del autónomo
  await downloaded(gina.context(), (await original.getAttribute("href")) ?? "");
  await expectReadOnly(gina);

  await openGestor(gastosPage);
  await expect(activity(gastosPage).getByText("Tu gestor descargó el original de un documento").first()).toBeVisible();
});

// --- La ficha (AC-11 a AC-14, AC-20) -----------------------------------------------------------------------------------------------

test("Ficha · facturas: lista, detalle, rectificativa y PDF real por URL firmada", async ({ pageAs, gastosPage, gastosUser, biller, gestor }) => {
  const issued = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: `Servicio del gestor ${randomUUID().slice(0, 6)}`, base_cents: 12_345 });
  const rectified = await biller.invoices.rectify(issued.id, 6_000);
  expect(issued.pdf_status).toBe("ready");
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);

  const gina = await pageAs("gina");
  await settle(gina);
  await gina.goto(ficha(ownerId, "facturas"));
  await expect(gina.getByRole("heading", { level: 1, name: gastosUser.name })).toBeVisible();
  const tabs = gina.getByRole("navigation", { name: "Secciones de la ficha" });
  await expect(tabs.getByRole("link")).toHaveText(["Facturas", "Gastos", "Documentos", "Trimestres", "Perfil y clientes", "Anotaciones"]);
  await expect(tabs.getByRole("link", { name: "Facturas" })).toHaveAttribute("aria-current", "page");
  const invoiceLink = (id: string) => shown(gina.locator(`a[href="/cartera/${ownerId}/facturas/${id}"]`)).first();
  await expect(invoiceLink(issued.id)).toBeVisible();
  await expect(invoiceLink(rectified.id)).toBeVisible();
  const links = await gina.locator('a[href*="/facturas/"]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") ?? ""));
  for (const href of links) expect(href.startsWith(`/cartera/${ownerId}/facturas/`), href).toBe(true); // nunca a las pantallas del autónomo
  await expectReadOnly(gina);

  // Detalle: en las tarjetas del móvil el enlace lleva «Factura » solo para lectores de pantalla (un rectángulo de 1 px): se pulsa sobre el texto visible.
  await invoiceLink(issued.id).click({ position: { x: 24, y: 8 } });
  await expect(gina.getByRole("heading", { level: 1, name: `Factura ${issued.display_number}` })).toBeVisible();
  await expect(gina.getByText("Emitida y bloqueada: una factura emitida no se edita ni se borra.")).toBeVisible();
  await expect(gina.getByRole("button", { name: /generar pdf/i })).toHaveCount(0);
  const pdf = gina.getByRole("link", { name: "Descargar PDF" });
  await expect(pdf).toHaveAttribute("href", `/cartera/${ownerId}/facturas/${issued.id}/pdf`);
  expect((await downloaded(gina.context(), `/cartera/${ownerId}/facturas/${issued.id}/pdf`)).body.subarray(0, 4).toString()).toBe("%PDF");
  await expectReadOnly(gina);

  // La rectificativa dice a quién rectifica y enlaza a su original dentro de la ficha.
  await gina.goto(`/cartera/${ownerId}/facturas/${rectified.id}`);
  await expect(gina.getByRole("heading", { level: 1, name: new RegExp(rectified.display_number) })).toBeVisible();
  await expect(gina.getByText(/Rectifica la factura/)).toBeVisible();
  await expect(gina.locator(`a[href="/cartera/${ownerId}/facturas/${issued.id}"]`).first()).toBeVisible();

  await openGestor(gastosPage);
  await expect(activity(gastosPage).getByText("Tu gestor descargó el PDF de una factura").first()).toBeVisible();
});

test("Ficha · gastos con el anulado rotulado, perfil con IBAN, clientes archivados y trimestres iguales a los del autónomo", async ({
  pageAs,
  gastosPage,
  gastosUser,
  biller,
  ledger,
  gestor,
}) => {
  const tag = randomUUID().slice(0, 6);
  const live = `Gasto vigente ${tag}`;
  const gone = `Gasto anulado ${tag}`;
  await ledger.create(live, madridToday(), 1_234);
  await ledger.void((await ledger.create(gone, madridToday(), 2_345)).id);
  await biller.profile.save({ ...BILLER_PROFILE, iban: IBAN });
  await biller.clientsApi.archive(biller.clients.noAddress.id);
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);

  const gina = await pageAs("gina");
  await settle(gina);

  // Gastos: el vigente y el anulado (rotulado); el gasto no tiene detalle para el gestor, así que su nombre no es un enlace.
  await gina.goto(ficha(ownerId, "gastos"));
  await expect(shown(gina.getByText(live)).first()).toBeVisible();
  const voided = shown(gina.getByRole("article").filter({ hasText: gone }).or(gina.getByRole("row").filter({ hasText: gone }))).first();
  await expect(voided.getByText("Anulado", { exact: true }).first()).toBeVisible();
  await expect(gina.getByRole("link", { name: live })).toHaveCount(0);
  await expectReadOnly(gina);

  // Perfil y clientes: el IBAN se ve (P-01), las series y el cliente archivado, marcado.
  await gina.goto(ficha(ownerId, "perfil"));
  await expect(gina.getByRole("heading", { level: 2, name: "Perfil del negocio" })).toBeVisible();
  await expect(gina.getByText(IBAN)).toBeVisible();
  await expect(gina.getByText(BILLER_PROFILE.legal_name)).toBeVisible();
  await expect(gina.getByRole("heading", { level: 3, name: /^Serie / }).first()).toBeVisible();
  // La cuenta del worker acumula clientes archivados con el mismo nombre de otras pruebas: se comprueba que el cliente archivado sale marcado con texto.
  await expect(gina.getByRole("listitem").filter({ hasText: "Sin Domicilio S.L." }).getByText("Archivado", { exact: true }).first()).toBeVisible();
  await expectReadOnly(gina);

  // Trimestres: el mismo borrador que ve el autónomo, casilla a casilla y con los documentos de cada una; los enlaces van a la ficha.
  for (const model of ["303", "130"] as const) {
    const query = model === "130" ? "&model=130" : "";
    await settle(gastosPage);
    await gastosPage.goto(`/trimestres?${query.slice(1)}`);
    await gina.goto(ficha(ownerId, "trimestres", query));
    const theirs = await sheetText(gina, model === "130" ? "modelo-130" : "modelo-303");
    expect(theirs.length).toBeGreaterThan(200);
    expect(theirs, `modelo ${model}`).toBe(await sheetText(gastosPage, model === "130" ? "modelo-130" : "modelo-303"));
    const hrefs = await gina.locator(`section[aria-labelledby="modelo-${model}"] a`).evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") ?? ""));
    for (const href of hrefs) expect(href.startsWith(`/cartera/${ownerId}`), href).toBe(true);
  }
  await gina.goto(ficha(ownerId, "trimestres", "&year=2999&quarter=1")); // futuro: lo explica el servidor, en el mismo sitio
  await expect(gina.getByRole("status")).toBeVisible();
  await expectReadOnly(gina);
});

test("Ficha · anotaciones: errores junto al campo, general y ligada a una factura, y las ve el autónomo", async ({ pageAs, gastosPage, gastosUser, biller, gestor }) => {
  const issued = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: `Servicio anotado ${randomUUID().slice(0, 6)}`, base_cents: 5_000 });
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);
  const tag = randomUUID().slice(0, 6);
  const general = `Anotación general ${tag}`;
  const linked = `Anotación sobre la factura ${tag}`;

  const gina = await pageAs("gina");
  await settle(gina);
  await gina.goto(ficha(ownerId, "anotaciones"));
  const field = gina.getByLabel("Anotación para el autónomo");
  await gina.getByRole("button", { name: "Añadir anotación" }).click();
  await expect(gina.locator("#anotacion-body-error")).toBeVisible();
  await expect(field).toHaveAttribute("aria-invalid", "true");
  await settleForm(gina); // ver `settleForm`: el formulario se reinicia un instante después del error
  await field.fill(general);
  await gina.getByRole("button", { name: "Añadir anotación" }).click();
  await expect(gina.getByText("Anotación guardada.")).toBeVisible();
  await expect(gina.getByRole("region", { name: "Tus anotaciones" }).getByText(general)).toBeVisible();

  await gina.goto(`/cartera/${ownerId}/facturas/${issued.id}`);
  await gina.getByLabel("Anotación sobre esta factura").fill(linked);
  await gina.getByRole("button", { name: "Añadir anotación" }).click();
  await expect(gina.getByText("Anotación guardada.")).toBeVisible();
  await gina.goto(ficha(ownerId, "anotaciones"));
  const notes = gina.getByRole("region", { name: "Tus anotaciones" });
  await expect(notes.getByText(linked)).toBeVisible();
  await expect(notes.getByRole("link", { name: "Sobre una factura" }).first()).toHaveAttribute("href", `/cartera/${ownerId}/facturas/${issued.id}`);
  await expect(notes.getByRole("button")).toHaveCount(0); // solo se añaden: ni editar ni borrar
  await expectReadOnly(gina);

  // El autónomo las lee en «Mi gestor» con el correo de su gestor, el enlace a su factura y la entrada de actividad; tampoco puede cambiarlas.
  await openGestor(gastosPage);
  const received = gastosPage.getByRole("region", { name: "Anotaciones de tu gestor" });
  await expect(received.getByText(general)).toBeVisible();
  await expect(received.getByText(GINA).first()).toBeVisible();
  await expect(received.locator(`a[href="/facturas/${issued.id}"]`).first()).toBeVisible();
  await expect(received.getByRole("button")).toHaveCount(0);
  await expect(activity(gastosPage).getByText("Tu gestor añadió una anotación").first()).toBeVisible();
});

// --- Acceso, solo lectura y aspecto (AC-09, AC-14, AC-21, AC-22, AC-24) ----------------------------------------------------------------

test("Ficha · otro gestor, un autónomo y el administrador no entran; revocar corta la ficha y la descarga al instante; y todo cabe a 390 y 1.440 px", async ({
  pageAs,
  gusPage,
  gastosPage,
  gastosUser,
  biller,
  gestor,
}) => {
  const issued = await biller.invoices.issue({ client_id: biller.clients.national.id, concept: `Servicio del acceso ${randomUUID().slice(0, 6)}`, base_cents: 7_000 });
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);
  const pdfHref = `/cartera/${ownerId}/facturas/${issued.id}/pdf`;

  // Quien no es su gestor: el mismo «no encontrado» (también para el PDF); un autónomo y el administrador, a /403.
  await gusPage.goto(ficha(ownerId, "facturas"));
  await expect(gusPage.getByRole("heading", { level: 1, name: "No encontramos a ese autónomo" })).toBeVisible();
  await expect(gusPage.getByText(gastosUser.name)).toHaveCount(0);
  expect((await gusPage.context().request.get(pdfHref, { maxRedirects: 0 })).status()).toBe(404);
  for (const role of ["alicia", "adan"] as const) {
    const page = await pageAs(role);
    await settle(page);
    await page.goto(ficha(ownerId, "facturas"));
    await expect(page).toHaveURL("/403");
  }

  // Aspecto y teclado de toda la ficha: sin scroll horizontal, campos etiquetados, consola limpia (la vigila `pageAs`) y solo lectura.
  const gina = await pageAs("gina");
  await settle(gina);
  for (const url of ["/cartera", ficha(ownerId, "facturas"), ficha(ownerId, "gastos"), ficha(ownerId, "documentos"), ficha(ownerId, "trimestres"), ficha(ownerId, "trimestres", "&model=130"), ficha(ownerId, "perfil"), ficha(ownerId, "anotaciones"), `/cartera/${ownerId}/facturas/${issued.id}`]) {
    await gina.goto(url);
    await expect(gina.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalScroll(gina);
    await expectEveryFieldLabelled(gina);
    if (url.startsWith("/cartera/")) await expectReadOnly(gina);
  }
  const tabs = gina.getByRole("navigation", { name: "Secciones de la ficha" });
  await gina.goto(ficha(ownerId, "facturas"));
  await tabs.getByRole("link", { name: "Gastos" }).focus(); // las pestañas se recorren con el teclado
  await gina.keyboard.press("Enter");
  await expect(gina).toHaveURL(/tab=gastos/);
  await expect(tabs.getByRole("link", { name: "Gastos" })).toHaveAttribute("aria-current", "page");
  await settle(gastosPage);
  await openGestor(gastosPage);
  await expectNoHorizontalScroll(gastosPage);
  await expectEveryFieldLabelled(gastosPage);

  // Revocar: la petición siguiente ya no ve nada (sin caché de vínculo, AC-24), ni la ficha ni el archivo; y la cartera ya no lo lista.
  await gestor.owner.revokeOpen();
  await gina.goto(ficha(ownerId, "facturas"));
  await expect(gina.getByRole("heading", { level: 1, name: "No encontramos a ese autónomo" })).toBeVisible();
  expect((await gina.context().request.get(pdfHref, { maxRedirects: 0 })).status()).toBe(404);
  await gina.goto("/cartera");
  await expect(gina.getByRole("heading", { level: 1, name: "Hola, Gina" })).toBeVisible();
  await expect(portfolio(gina).getByText(gastosUser.name)).toHaveCount(0);
});

// --- Listas largas (AC-23): solo en un proyecto, porque emite 51 facturas --------------------------------------------------------------

test("Ficha · con más de 50 facturas y 50 gastos hay página siguiente y cursor", async ({ pageAs, gastosUser, biller, ledger, gestor }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-1440", "Emite 51 facturas por la API: solo en un proyecto para no llenar la base con cientos por batería (la lógica de páginas la fijan las unitarias).");
  test.setTimeout(300_000);
  const tag = randomUUID().slice(0, 6);
  for (let n = 1; n <= 51; n += 1) {
    await biller.invoices.issue({ client_id: biller.clients.national.id, concept: `Paginación ${tag} ${n}`, base_cents: 100 + n });
    await ledger.create(`Gasto paginación ${tag} ${n}`, madridToday(), 100 + n);
  }
  await gestor.owner.invite(GINA);
  const ownerId = await gestor.gina.acceptFrom(gastosUser.name);

  const gina = await pageAs("gina");
  await settle(gina);
  const invoiceLinks = (page: Page) => shown(page.locator(`a[href^="/cartera/${ownerId}/facturas/"]`));
  await gina.goto(ficha(ownerId, "facturas"));
  await expect(invoiceLinks(gina)).toHaveCount(50);
  await expect(gina.getByText("Página 1", { exact: true })).toBeVisible();
  await expect(gina.getByRole("link", { name: "Página anterior" })).toHaveCount(0);
  await gina.getByRole("link", { name: "Página siguiente" }).click();
  await expect(gina).toHaveURL(/pagina=2/);
  await expect(gina.getByText("Página 2", { exact: true })).toBeVisible();
  expect(await invoiceLinks(gina).count()).toBeGreaterThanOrEqual(1);
  await expect(gina.getByRole("link", { name: "Página anterior" })).toBeVisible();
  await expectNoHorizontalScroll(gina);

  await gina.goto(ficha(ownerId, "gastos"));
  await expect(gina.locator("tbody tr")).toHaveCount(50);
  await gina.getByRole("link", { name: "Ver gastos anteriores" }).click();
  await expect(gina).toHaveURL(/cursor=/);
  await expect(gina.getByRole("link", { name: "Volver a los más recientes" })).toBeVisible();
  await gina.getByRole("link", { name: "Volver a los más recientes" }).click();
  await expect(gina.locator("tbody tr")).toHaveCount(50);
});
