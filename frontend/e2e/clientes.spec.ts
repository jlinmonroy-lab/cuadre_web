// SPEC-W-006 · Clientes: NIF, ámbito y VIES simulado, en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px).
// AC-01 a AC-10, AC-15 y AC-17 en un navegador de verdad (AC-11 a AC-14 y AC-18 son de la API y la base; AC-16 está en `roles.spec.ts`).
//
// Usan `gastosPage`, la cuenta de `usuario` del worker, que comparten estas pruebas y las de Gastos y Perfil: el fixture `clients` archiva sus
// clientes al empezar y al terminar (T6-10), porque un cliente no se borra y el NIF es único entre los activos. La interfaz no valida nada fiscal:
// estas pruebas comprueban que enseña lo que decide el servidor. NIF y NIF-IVA son sintéticos con dígitos de control válidos.
//
// Next conserva oculta la pantalla anterior al navegar: los localizadores piden siempre lo VISIBLE, y las esperas son por un efecto concreto (una
// fila, un texto que antes no estaba), no por «Cliente añadido.», que sigue en pantalla de la alta anterior.
import type { Locator, Page } from "@playwright/test";

import { expect, settle, test } from "./helpers/fixtures";
import { shown, text } from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";

const CIF_A = "B00000018";
const CIF_B = "B00000026";
const CIF_C = "A00000026";
const VAT_DE = "DE534861408";
const VAT_FR = "FR89195505110";
const VAT_EL = "EL088590212";

const MSG_NIF = "El NIF no es válido: revisa el dígito o la letra de control.";
const MSG_NOT_SPANISH = "Escribe un NIF, NIE o CIF español.";
const MSG_VAT = "El NIF-IVA no es válido o no corresponde al país elegido.";
const MSG_TAKEN = "Ya tienes otro cliente activo con ese NIF o identificador fiscal.";

type Draft = { name?: string; kind?: "business" | "individual"; country?: string; tax?: string; address?: string };

async function openClientes(page: Page, archived = false): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto(archived ? "/clientes?archivados=1" : "/clientes");
  await expect(page.getByRole("heading", { level: 1, name: "Clientes" })).toBeVisible();
}

const addField = (page: Page, name: string): Locator => shown(page.locator(`#cliente-nuevo-${name}`));
const addError = (page: Page, name: string): Locator => shown(page.locator(`#cliente-nuevo-${name}-error`));
/** El resumen de errores del formulario de alta (el servidor devuelve todos a la vez). */
const summary = (page: Page): Locator => shown(page.locator("form", { has: page.locator("#cliente-nuevo-name") }).getByRole("alert"));
const idLabel = (page: Page): Locator => shown(page.locator("label[for='cliente-nuevo-tax_id']"));
const state = (page: Page, message: string | RegExp): Locator => shown(page.getByRole("status").filter({ hasText: message }));

/** La fila (tabla) o la tarjeta (móvil) de un cliente: las dos vistas están en el DOM y solo una se ve. */
const rows = (page: Page): Locator => shown(page.locator("article, tbody tr"));
const clientRow = (page: Page, name: string): Locator => rows(page).filter({ hasText: name });
/** Las insignias de ámbito y VIES de una fila (en móvil el editor vive dentro de la tarjeta y trae sus propios `li` de error). */
const badges = (row: Locator): Locator => row.locator('ul[aria-label="Ámbito y comprobación de VIES"] > li');
/** El editor abierto (solo hay uno a la vez): vive dentro de su tarjeta o en la fila de debajo de la tabla. */
const editor = (page: Page): Locator => shown(page.locator("form").filter({ has: page.getByRole("button", { name: "Guardar cliente" }) }));

async function openAdd(page: Page): Promise<void> {
  if (!(await addField(page, "name").isVisible())) await shown(page.locator("summary", { hasText: "Añadir cliente" })).click();
  await expect(addField(page, "name")).toBeVisible();
}

async function fillAdd(page: Page, draft: Draft): Promise<void> {
  await openAdd(page);
  await addField(page, "name").fill(draft.name ?? "");
  await addField(page, "kind").selectOption(draft.kind ?? "business");
  await addField(page, "country").selectOption(draft.country ?? "");
  await addField(page, "tax_id").fill(draft.tax ?? "");
  await addField(page, "address").fill(draft.address ?? "");
}

const submitAdd = (page: Page): Locator => shown(page.getByRole("button", { name: "Añadir cliente" }));

async function addClient(page: Page, draft: Draft): Promise<void> {
  await fillAdd(page, draft);
  await submitAdd(page).click();
}

/** Alta que debe salir bien: espera a que la fila exista. */
async function addOk(page: Page, draft: Draft): Promise<Locator> {
  await addClient(page, draft);
  const row = clientRow(page, draft.name ?? "");
  await expect(row).toBeVisible();
  return row;
}

// --- AC-01 a AC-03 · AC-07 -------------------------------------------------------------------------------------------------------

test("un cliente de cada ámbito (AC-01, AC-02, AC-03, AC-07): nacional, UE, Grecia con EL, México y un particular de EE. UU.", async ({ gastosPage: page, clients }) => {
  // AC-02: nada sale de la aplicación (el VIES es simulado: sin red).
  const external: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && !["localhost", "127.0.0.1"].includes(url.hostname)) external.push(url.hostname);
  });
  await openClientes(page);

  const national = await addOk(page, { name: "Estudio Norte S.L.", country: "ES", tax: ` ${CIF_A.toLowerCase()} ` }); // minúscula y con espacios
  await expect(national).toContainText(CIF_A);
  await expect(badges(national)).toHaveText(["Nacional", /No aplica/]);

  const german = await addOk(page, { name: "Kreativ GmbH", country: "DE", tax: VAT_DE });
  await expect(badges(german)).toHaveText(["UE", "VIES: Válido (simulado)"]); // el «VIES:» es para el lector de pantalla

  const greek = await addOk(page, { name: "Hellas AE", country: "GR", tax: `gr${VAT_EL.slice(2)}` }); // GR↔EL: se guarda con el prefijo EL
  await expect(greek).toContainText(VAT_EL);
  await expect(badges(greek)).toHaveText(["UE", /Válido \(simulado\)/]);

  const mexican = await addOk(page, { name: "Taller Zócalo", country: "MX", tax: "xaxx 010101-000" });
  await expect(mexican).toContainText("XAXX010101000");
  await expect(badges(mexican)).toHaveText(["Fuera de la UE", /No aplica/]);

  const american = await addOk(page, { name: "Jane Doe", kind: "individual", country: "US" }); // un particular puede no tener identificador
  await expect(badges(american)).toHaveText(["Fuera de la UE", /No aplica/]);

  // Lo que se ve es lo que decidió el servidor (y no lo que escribió la persona).
  const saved = Object.fromEntries((await clients.list()).map((client) => [client.name, client]));
  expect(saved["Estudio Norte S.L."]).toMatchObject({ scope: "national", vies_status: "not_applicable", tax_id: CIF_A });
  expect(saved["Kreativ GmbH"]).toMatchObject({ scope: "eu", vies_status: "valid_simulated", tax_id: VAT_DE });
  expect(saved["Hellas AE"]).toMatchObject({ scope: "eu", vies_status: "valid_simulated", tax_id: VAT_EL });
  expect(saved["Taller Zócalo"]).toMatchObject({ scope: "non_eu", vies_status: "not_applicable", tax_id: "XAXX010101000" });
  expect(saved["Jane Doe"]).toMatchObject({ scope: "non_eu", vies_status: "not_applicable", tax_id: null });
  expect(external, "la aplicación no debe llamar a ningún servicio externo").toEqual([]);

  // Ordenados por nombre en español.
  const names = await rows(page).evaluateAll((items) => items.map((item) => item.textContent ?? ""));
  const order = ["Estudio Norte S.L.", "Hellas AE", "Jane Doe", "Kreativ GmbH", "Taller Zócalo"].map((name) => names.findIndex((value) => value.includes(name)));
  expect(order, "la lista debe ir por nombre").toEqual([...order].sort((a, b) => a - b));
});

// --- AC-04 · AC-05 · AC-06 -------------------------------------------------------------------------------------------------------

const BAD_NIFS: { why: string; draft: Draft; message: string }[] = [
  { why: "letra de control equivocada", draft: { country: "ES", tax: "B00000019" }, message: MSG_NIF },
  { why: "un NIF-IVA de la UE en un cliente nacional", draft: { country: "ES", tax: VAT_FR }, message: MSG_NOT_SPANISH },
  { why: "un NIF-IVA francés para un cliente alemán", draft: { country: "DE", tax: VAT_FR }, message: MSG_VAT },
];

for (const { why, draft, message } of BAD_NIFS) {
  test(`NIF inválido (AC-04): ${why} sale junto al NIF, con el foco en el resumen, sin repetir lo escrito y sin guardar nada`, async ({ gastosPage: page, clients }) => {
    await openClientes(page);
    await addClient(page, { name: "Cliente con NIF malo", ...draft });

    await expect(addError(page, "tax_id")).toContainText(message);
    await expect(summary(page)).toBeFocused();
    await expect(summary(page)).toContainText(message);
    await expect(addField(page, "tax_id")).toHaveAttribute("aria-invalid", "true");
    await expect(addField(page, "tax_id")).toHaveAttribute("aria-describedby", /cliente-nuevo-tax_id-error/);
    await expect(summary(page)).not.toContainText(draft.tax ?? "—");
    await expect(addField(page, "tax_id")).toHaveValue(draft.tax ?? ""); // lo tecleado se conserva para corregirlo
    expect(await clients.list(), "no se guardó nada").toEqual([]);
  });
}

test("particulares (AC-06): sin NIF se crea; con el NIF mal sale el error junto al NIF", async ({ gastosPage: page, clients }) => {
  await openClientes(page);
  const row = await addOk(page, { name: "Ana Particular", kind: "individual", country: "ES" });
  await expect(badges(row)).toHaveText(["Nacional", /No aplica/]);

  await addClient(page, { name: "Beto Particular", kind: "individual", country: "ES", tax: "12345678A" });
  await expect(addError(page, "tax_id")).toContainText(MSG_NIF);
  expect((await clients.list()).map((client) => client.name)).toEqual(["Ana Particular"]);
});

test("tras un error y un éxito el aviso «Cliente añadido.» se ve: el desplegable no se cierra (AC-15)", async ({ gastosPage: page, clients }) => {
  await openClientes(page);
  await addClient(page, { name: "Corregido S.L.", country: "ES", tax: "B00000019" });
  await expect(addError(page, "tax_id")).toContainText(MSG_NIF);

  await addField(page, "tax_id").fill(CIF_A);
  await submitAdd(page).click();
  await expect(clientRow(page, "Corregido S.L.")).toBeVisible();
  await expect(text(page, "Cliente añadido.")).toBeVisible(); // con el desplegable cerrado, el aviso quedaría escondido
  await expect(addField(page, "name")).toBeVisible();
  await expect(addField(page, "name")).toHaveValue(""); // y el formulario queda vacío para el siguiente
  expect((await clients.list()).map((client) => client.name)).toEqual(["Corregido S.L."]);
});

test("todos los errores a la vez (AC-05): nombre y país, uno junto a cada campo y en el orden de la pantalla, conservando lo elegido", async ({ gastosPage: page, clients }) => {
  await openClientes(page);
  await addClient(page, { name: "", kind: "individual", country: "" });

  await expect(addError(page, "name")).toContainText("nombre");
  await expect(addError(page, "country")).toContainText("país");
  await expect(summary(page)).toBeFocused();
  const items = summary(page).getByRole("listitem");
  await expect(items).toHaveCount(2);
  await expect(items.nth(0)).toContainText("nombre"); // el orden de la pantalla: nombre y después país
  await expect(items.nth(1)).toContainText("país");
  await expect(addField(page, "name")).toHaveAttribute("aria-invalid", "true");
  await expect(addField(page, "country")).toHaveAttribute("aria-invalid", "true");
  await expect(addField(page, "kind")).toHaveValue("individual"); // el tipo elegido sobrevive al error
  expect(await clients.list(), "no se creó ninguno").toEqual([]);
});

// --- AC-08 ------------------------------------------------------------------------------------------------------------------------

test("un NIF por persona (AC-08): repetirlo da un 409 junto al NIF al crear, al editar y al reactivar; en un archivado no cuenta", async ({ gastosPage: page, clients }) => {
  const first = await clients.create({ name: "Primero S.L.", kind: "business", country: "ES", tax_id: CIF_A });
  await clients.create({ name: "Segundo S.L.", kind: "business", country: "ES", tax_id: CIF_B });
  await openClientes(page);

  // Crear: el resumen solo enlaza al campo (el titular sería el mismo texto leído dos veces).
  await addClient(page, { name: "Repetido S.L.", country: "ES", tax: CIF_A.toLowerCase() });
  await expect(addError(page, "tax_id")).toContainText(MSG_TAKEN);
  await expect(summary(page).getByText(MSG_TAKEN)).toHaveCount(1);
  await expect(summary(page)).toBeFocused();
  await expect(clientRow(page, "Repetido S.L.")).toHaveCount(0);

  // Editar: el segundo intenta quedarse con el NIF del primero.
  await clientRow(page, "Segundo S.L.").getByRole("button", { name: "Editar el cliente Segundo S.L." }).click();
  await editor(page).locator("[name=tax_id]").fill(CIF_A);
  await editor(page).getByRole("button", { name: "Guardar cliente" }).click();
  await expect(shown(editor(page).locator("[id$='-tax_id-error']"))).toContainText(MSG_TAKEN);
  await editor(page).getByRole("button", { name: "Cerrar" }).click();

  // Reactivar: archivado el primero, su NIF queda libre; se crea otro con él y reactivar el primero da el error en su fila.
  await clients.archive(first.id);
  await openClientes(page);
  await addOk(page, { name: "Nuevo dueño S.L.", country: "ES", tax: CIF_A });
  await openClientes(page, true);
  await clientRow(page, "Primero S.L.").getByRole("button", { name: "Reactivar el cliente Primero S.L." }).click();
  await expect(clientRow(page, "Primero S.L.").getByText(MSG_TAKEN)).toBeVisible();
  await expect(clientRow(page, "Primero S.L.")).toContainText("Archivado"); // sigue archivado
});

// --- AC-09 · AC-10 ----------------------------------------------------------------------------------------------------------------

test("editar, archivar y reactivar (AC-09, AC-10): cambia solo la fila editada, el archivado no se edita y no hay borrado", async ({ gastosPage: page, clients }) => {
  await clients.create({ name: "Alfa S.L.", kind: "business", country: "ES", tax_id: CIF_A });
  await clients.create({ name: "Beta S.L.", kind: "business", country: "ES", tax_id: CIF_B });
  await clients.create({ name: "Gamma S.L.", kind: "business", country: "ES", tax_id: CIF_C });
  await openClientes(page);
  await expect(rows(page)).toHaveCount(3);

  // Editar la del medio: de España a Francia con un NIF-IVA francés.
  await clientRow(page, "Beta S.L.").getByRole("button", { name: "Editar el cliente Beta S.L." }).click();
  const form = editor(page);
  await form.locator("[name=country]").selectOption("FR");
  await expect(shown(form.locator("label[for$='-tax_id']"))).toHaveText("NIF-IVA"); // el rótulo sigue al país elegido
  await form.locator("[name=tax_id]").fill(VAT_FR);
  await form.getByRole("button", { name: "Guardar cliente" }).click();
  await expect(form.getByText("Cliente guardado.")).toBeVisible();
  await expect(badges(clientRow(page, "Beta S.L."))).toHaveText(["UE", /Válido \(simulado\)/]);
  await expect(form.locator("[name=country]")).toHaveValue("FR"); // tras guardar, el selector conserva lo guardado
  await expect(form.locator("[name=kind]")).toHaveValue("business");
  await expect(shown(form.locator("label[for$='-tax_id']"))).toHaveText("NIF-IVA");
  for (const other of ["Alfa S.L.", "Gamma S.L."]) {
    await expect(badges(clientRow(page, other))).toHaveText(["Nacional", /No aplica/]); // las demás no cambian
  }

  // Editar con un NIF malo: no guarda nada.
  await form.locator("[name=country]").selectOption("ES");
  await form.locator("[name=tax_id]").fill("B00000019");
  await form.getByRole("button", { name: "Guardar cliente" }).click();
  await expect(shown(form.locator("[id$='-tax_id-error']"))).toContainText(MSG_NIF);
  await expect(badges(clientRow(page, "Beta S.L."))).toHaveText(["UE", /Válido \(simulado\)/]);
  await form.getByRole("button", { name: "Cerrar" }).click();
  await expect(editor(page)).toHaveCount(0);

  // Archivar la de abajo: aviso en la lista y la fila desaparece.
  await clientRow(page, "Gamma S.L.").getByRole("button", { name: "Archivar el cliente Gamma S.L." }).click();
  await expect(state(page, "Cliente archivado. Gamma S.L.")).toBeVisible();
  await expect(clientRow(page, "Gamma S.L.")).toHaveCount(0);
  await expect(rows(page)).toHaveCount(2);

  // Con archivados: la enseña marcada, con «Reactivar», sin «Editar» y sin ningún botón de borrar.
  await shown(page.getByRole("link", { name: "Mostrar archivados" })).click();
  await expect(page).toHaveURL(/\/clientes\?archivados=1$/);
  const archived = clientRow(page, "Gamma S.L.");
  await expect(archived).toContainText("Archivado");
  await expect(archived.getByRole("button", { name: "Editar el cliente Gamma S.L." })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Borrar|Eliminar/ })).toHaveCount(0);
  await archived.getByRole("button", { name: "Reactivar el cliente Gamma S.L." }).click();
  await expect(state(page, "Cliente reactivado. Gamma S.L.")).toBeVisible();
  await expect(clientRow(page, "Gamma S.L.")).not.toContainText("Archivado");
  await expect(clientRow(page, "Gamma S.L.").getByRole("button", { name: "Archivar el cliente Gamma S.L." })).toBeVisible();

  await shown(page.getByRole("link", { name: "Ocultar archivados" })).click();
  await expect(page).toHaveURL(/\/clientes$/);
});

test("lista vacía: una cuenta sin clientes lo dice y ofrece el alta", async ({ gastosPage: page, clients }) => {
  void clients;
  await openClientes(page);
  await expect(text(page, /Todavía no tienes clientes activos/)).toBeVisible();
  await expect(rows(page)).toHaveCount(0);
  await openAdd(page);
});

// --- AC-15 · AC-17 ----------------------------------------------------------------------------------------------------------------

test("el rótulo del identificador cambia con el país y el tipo (AC-15): NIF, NIF-IVA e Identificador fiscal", async ({ gastosPage: page, clients }) => {
  void clients;
  await openClientes(page);
  await openAdd(page);
  await expect(idLabel(page)).toHaveText("NIF"); // un cliente nuevo nace en España y como empresa
  for (const [country, kind, label] of [
    ["DE", "business", "NIF-IVA"],
    ["GR", "business", "NIF-IVA"],
    ["DE", "individual", "Identificador fiscal"],
    ["MX", "business", "Identificador fiscal"],
    ["ES", "individual", "NIF"],
    ["", "business", "NIF o identificador fiscal"],
  ] as const) {
    await addField(page, "country").selectOption(country);
    await addField(page, "kind").selectOption(kind);
    await expect(idLabel(page), `${country || "sin país"} / ${kind}`).toHaveText(label);
  }
});

test("nombres de país (AC-17): los 249 tienen nombre distinto del código en este motor y el selector va por nombre, sin comparar nombres entre motores", async ({ gastosPage: page, clients }) => {
  void clients;
  await openClientes(page);
  await openAdd(page);
  const options = await addField(page, "country")
    .locator("option")
    .evaluateAll((items) => items.map((item) => ({ value: (item as HTMLOptionElement).value, text: item.textContent ?? "" })));
  expect(options).toHaveLength(250); // 249 países y «Elige un país»
  expect(options[0]).toMatchObject({ value: "" });
  const countries = options.slice(1);
  expect(new Set(countries.map((option) => option.value)).size, "códigos repetidos").toBe(249);
  expect(countries.filter((option) => option.text === option.value || option.text.trim() === ""), "países sin nombre").toEqual([]);

  // El propio motor también sabe nombrarlos (los nombres que se ven son los del servidor y pueden diferir de los de cada navegador en cuatro códigos).
  const unnamed = await page.evaluate((codes) => {
    const names = new Intl.DisplayNames(["es"], { type: "region" });
    return codes.filter((code) => (names.of(code) ?? code) === code);
  }, countries.map((option) => option.value));
  expect(unnamed, "códigos sin nombre en español en este motor").toEqual([]);

  const unsorted = await page.evaluate((texts) => {
    const collator = new Intl.Collator("es");
    return texts.filter((value, index) => index > 0 && collator.compare(texts[index - 1] ?? "", value) > 0);
  }, countries.map((option) => option.text));
  expect(unsorted, "el selector debe ir ordenado por nombre").toEqual([]);
});

test("hidratación (AC-17): con clientes en los países que cada motor nombra distinto, el HTML del servidor y el navegador coinciden", async ({ gastosPage: page, clients }) => {
  // Chromium nombra FK, HK, MO y PS distinto que Node (y cada motor ordena a su manera): si la lista o el selector calcularan los nombres en el
  // navegador, la carga dura daría un error de hidratación (React #418) que el fixture convierte en fallo. Los nombres salen del servidor.
  for (const [country, name] of [
    ["FK", "Falkland Ltd"],
    ["HK", "Hong Kong Ltd"],
    ["MO", "Macao Ltd"],
    ["PS", "Palestina Ltd"],
  ] as const) {
    await clients.create({ name, kind: "business", country, tax_id: `ID${country}1` });
  }
  await openClientes(page); // carga dura: es lo que hidrata
  await openAdd(page);
  for (const [country, name] of [
    ["FK", "Falkland Ltd"],
    ["HK", "Hong Kong Ltd"],
    ["MO", "Macao Ltd"],
    ["PS", "Palestina Ltd"],
  ] as const) {
    const label = (await addField(page, "country").locator(`option[value="${country}"]`).textContent()) ?? "";
    expect(label, `el selector no nombra ${country}`).not.toBe("");
    await expect(clientRow(page, name), `la lista y el selector deben nombrar igual ${country}`).toContainText(label);
  }
});

test("interfaz (AC-15): sin scroll horizontal, campos etiquetados, tarjetas o tabla según el ancho y sin errores de consola", async ({ gastosPage: page, clients }, testInfo) => {
  await clients.create({ name: "Alfa S.L.", kind: "business", country: "ES", tax_id: CIF_A });
  await clients.create({ name: "Kreativ GmbH", kind: "business", country: "DE", tax_id: VAT_DE });
  await openClientes(page);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
  const wide = testInfo.project.use.viewport!.width >= 1280;
  await expect(page.getByRole("table", { name: "Clientes por nombre" })).toHaveCount(wide ? 1 : 0);

  await addClient(page, { name: "", country: "" }); // errores a la vez
  await expect(summary(page)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);

  await clientRow(page, "Alfa S.L.").getByRole("button", { name: "Editar el cliente Alfa S.L." }).click();
  await expect(editor(page)).toBeVisible();
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
});

test("interfaz (AC-15): la tabla aparece desde 1.280 px y las tarjetas hasta 1.279, sin scroll horizontal", async ({ gastosPage: page, clients, browserName }) => {
  test.skip(browserName !== "chromium", "el ancho límite es el mismo en todos los motores: se comprueba en uno");
  await clients.create({ name: "Alfa S.L.", kind: "business", country: "ES", tax_id: CIF_A });
  await openClientes(page);
  for (const [width, table] of [
    [1279, false],
    [1280, true],
  ] as const) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("table", { name: "Clientes por nombre" })).toHaveCount(table ? 1 : 0);
    await expectNoHorizontalScroll(page);
  }
});

test("interfaz (AC-15): con el teclado se llega a todos los campos hasta «Añadir cliente», el foco se ve y se puede archivar", async ({ gastosPage: page, clients }) => {
  await clients.create({ name: "Alfa S.L.", kind: "business", country: "ES", tax_id: CIF_A });
  await openClientes(page);
  await openAdd(page);
  const first = addField(page, "name");
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
    if (await submitAdd(page).evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(submitAdd(page)).toBeFocused();
  for (const id of ["cliente-nuevo-name", "cliente-nuevo-kind", "cliente-nuevo-country", "cliente-nuevo-tax_id", "cliente-nuevo-address"]) {
    expect(visited, `el foco no pasó por ${id}`).toContain(id);
  }

  // Archivar sin ratón: foco en el botón y Enter.
  const archive = clientRow(page, "Alfa S.L.").getByRole("button", { name: "Archivar el cliente Alfa S.L." });
  const restingArchive = await signature(archive);
  await archive.focus();
  await expect(archive).toBeFocused();
  expect(await signature(archive), "el botón no muestra el foco").not.toBe(restingArchive);
  await page.keyboard.press("Enter");
  await expect(state(page, "Cliente archivado. Alfa S.L.")).toBeVisible();
  await expect(clientRow(page, "Alfa S.L.")).toHaveCount(0);
});
