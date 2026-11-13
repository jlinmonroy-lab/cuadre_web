// SPEC-W-014 AC-15 · La sección «Recordatorios» de /perfil, en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px).
//
// Usan `gastosPage`, la cuenta de `usuario` del worker, y el fixture `profile`, que restaura el perfil y los ajustes de recordatorios (activados y
// 10 días) al empezar y al terminar. La interfaz no decide el rango de la antelación: estas pruebas comprueban que enseña lo que decide el servidor.
import type { Locator, Page } from "@playwright/test";

import { expect, settle, test } from "./helpers/fixtures";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";

async function openPerfil(page: Page): Promise<void> {
  await settle(page);
  await page.goto("/perfil");
  await expect(page.getByRole("heading", { level: 1, name: "Perfil" })).toBeVisible();
}

const section = (page: Page): Locator => page.getByRole("region", { name: "Recordatorios" });
const toggle = (page: Page): Locator => section(page).getByLabel("Avisarme por correo antes de cada plazo");
const days = (page: Page): Locator => section(page).getByLabel("Días de antelación", { exact: true });
const save = (page: Page): Locator => section(page).getByRole("button", { name: "Guardar recordatorios" });
const saved = (page: Page): Locator => section(page).getByText("Recordatorios guardados.");
const daysError = (page: Page): Locator => section(page).locator("#recordatorios-lead_days-error");

test("valores por defecto: avisos activados y 10 días", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await expect(section(page).getByRole("heading", { level: 2, name: "Recordatorios" })).toBeVisible();
  await expect(toggle(page)).toBeChecked();
  await expect(days(page)).toHaveValue("10");
  await expect(section(page)).toContainText("orientativos");
});

test("desactivar y guardar: se confirma y persiste al recargar", async ({ gastosPage: page, profile }) => {
  await openPerfil(page);
  await toggle(page).uncheck();
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await expect(toggle(page)).not.toBeChecked();
  expect(await profile.readReminders()).toEqual({ enabled: false, lead_days: 10 });

  await openPerfil(page);
  await expect(toggle(page)).not.toBeChecked();
  await expect(days(page)).toHaveValue("10");
});

test("cambiar la antelación y guardar: se confirma, persiste y la API lo guarda", async ({ gastosPage: page, profile }) => {
  await openPerfil(page);
  await days(page).fill("14");
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await expect(days(page)).toHaveValue("14");
  await expect(toggle(page)).toBeChecked();
  expect(await profile.readReminders()).toEqual({ enabled: true, lead_days: 14 });

  await openPerfil(page);
  await expect(days(page)).toHaveValue("14");
});

for (const value of ["0", "31"]) {
  test(`${value} días: el servidor lo rechaza, el error sale junto al campo y no cambia lo guardado`, async ({ gastosPage: page, profile }) => {
    await openPerfil(page);
    await days(page).fill(value);
    await save(page).click();

    await expect(daysError(page)).toContainText("entre 1 y 30");
    await expect(days(page)).toHaveAttribute("aria-invalid", "true");
    await expect(days(page)).toHaveAttribute("aria-describedby", /recordatorios-lead_days-error/);
    await expect(days(page)).toHaveValue(value); // no se pierde lo tecleado
    await expect(saved(page)).toHaveCount(0);
    expect(await profile.readReminders()).toEqual({ enabled: true, lead_days: 10 });
  });
}

for (const value of ["", "abc", "7,5"]) {
  test(`«${value}» no es un número entero: error junto al campo sin guardar nada`, async ({ gastosPage: page, profile }) => {
    await openPerfil(page);
    await days(page).fill(value);
    await save(page).click();
    await expect(daysError(page)).toContainText("número entero");
    await expect(days(page)).toHaveAttribute("aria-invalid", "true");
    expect(await profile.readReminders()).toEqual({ enabled: true, lead_days: 10 });
  });
}

test("un error no deja la casilla en un estado distinto del que se veía", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await toggle(page).uncheck();
  await days(page).fill("99");
  await save(page).click();
  await expect(daysError(page)).toBeVisible();
  await expect(toggle(page)).not.toBeChecked();
});

test("tras corregir el error se guarda todo junto", async ({ gastosPage: page, profile }) => {
  await openPerfil(page);
  await toggle(page).uncheck();
  await days(page).fill("99");
  await save(page).click();
  await expect(daysError(page)).toBeVisible();
  await days(page).fill("5");
  await save(page).click();
  await expect(saved(page)).toBeVisible();
  await expect(daysError(page)).toHaveCount(0);
  expect(await profile.readReminders()).toEqual({ enabled: false, lead_days: 5 });
});

test("el formulario del perfil y el de recordatorios son independientes", async ({ gastosPage: page, profile }) => {
  await openPerfil(page);
  await days(page).fill("20");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Cambios guardados.")).toBeVisible();
  expect(await profile.readReminders()).toEqual({ enabled: true, lead_days: 10 }); // el otro botón no guarda los recordatorios
});

test("maqueta: todos los campos etiquetados y sin scroll horizontal", async ({ gastosPage: page, profile }) => {
  void profile;
  await openPerfil(page);
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
  await days(page).fill("0");
  await save(page).click();
  await expect(daysError(page)).toBeVisible();
  await expectEveryFieldLabelled(page);
  await expectNoHorizontalScroll(page);
});
