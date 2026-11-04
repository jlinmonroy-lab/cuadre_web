import { randomUUID } from "node:crypto";

import { expect, type Locator, type Page } from "@playwright/test";

import { FIRST_PASSWORD, type Person } from "./env";
import { waitForLink } from "./mailpit";

/** Correo sintético y único (RES-07: solo @example.test), para que ninguna prueba dependa de lo que dejó otra. */
export function uniqueEmail(tag: string): string {
  return `e2e-${tag}-${Date.now().toString(36)}-${randomUUID().slice(0, 8)}@example.test`;
}

/** Rellena y envía el formulario de /login (no espera a ningún resultado). */
export async function fillLogin(page: Page, email: string, password: string): Promise<void> {
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
}

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await fillLogin(page, email, password);
}

/** Registra una cuenta nueva por la interfaz y la confirma con el enlace del correo; termina dentro, en /inicio. */
export async function signUpAndConfirm(page: Page, account: { name: string; email: string; password?: string }): Promise<void> {
  await page.goto("/registro");
  await page.getByLabel("Nombre").fill(account.name);
  await page.getByLabel("Correo electrónico").fill(account.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(account.password ?? FIRST_PASSWORD);
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByRole("status")).toContainText("Te hemos enviado un correo");
  await page.goto((await waitForLink(account.email, "email")).toString());
  await expect(page).toHaveURL("/inicio");
}

/** Resumen de errores del formulario (hay otros `role=alert` en la página, p. ej. el anunciador de rutas de Next). */
export function formAlert(page: Page): Locator {
  return page.getByRole("alert").filter({ hasText: /Revisa estos datos|incorrectos|Demasiados|No hemos/ });
}

/** La navegación de un rol: sus apartados, cuáles son enlaces y cuáles están desactivados («Próximamente»). */
export async function expectNavigation(page: Page, person: Pick<Person, "nav" | "enabledNav">): Promise<void> {
  const items = page.getByRole("navigation", { name: "Apartados" }).getByRole("listitem");
  await expect(items).toHaveCount(person.nav.length);
  for (const label of person.nav) {
    const item = items.filter({ hasText: label });
    if (person.enabledNav.includes(label)) {
      await expect(item.getByRole("link", { name: label })).toBeVisible();
      await expect(item.locator('[aria-disabled="true"]')).toHaveCount(0);
    } else {
      await expect(item.getByRole("link")).toHaveCount(0);
      await expect(item.locator('[aria-disabled="true"]')).toContainText("Próximamente");
    }
  }
}
