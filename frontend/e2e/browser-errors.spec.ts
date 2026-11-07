// El vigilante de errores del navegador (`watchBrowserErrors`, que usan todas las pruebas) cuenta cualquier `console.error` o excepción de
// página, salvo la precarga RSC que WebKit registra cuando una navegación la cancela (primer CI, SPEC-W-003 B.7). Estas pruebas fijan los dos
// lados —lo que no cuenta y lo que sigue contando— con el propio motor: si el filtro se ensancha o desaparece, fallan.
//
// Usan el `test` de Playwright y no el de `helpers/fixtures`, cuyo `page` hace fallar la prueba al ver precisamente estos errores.
import { expect, test, type Page } from "@playwright/test";

import { watchBrowserErrors } from "./helpers/fixtures";

/** El mensaje tal como lo mostró el CI (Playwright separa «Fetch API cannot load http» de lo demás y se come una barra). */
const CANCELLED = "/localhost:3000/admin?_rsc=qPZzjMbbkwVJZ1Df due to access control checks.";

/** Lanza una excepción de página y espera a que el navegador la haya informado (el vigilante se suscribió antes, así que ya la ha visto). */
async function raise(page: Page, message: string): Promise<void> {
  const reported = page.waitForEvent("pageerror");
  await page.evaluate((text) => {
    setTimeout(() => {
      throw new Error(text);
    }, 0);
  }, message);
  await reported;
}

test("una precarga RSC cancelada: en WebKit no cuenta como error; en los demás motores sí", async ({ page, browserName }) => {
  await page.goto("/login");
  const errors = watchBrowserErrors(page);

  await raise(page, CANCELLED);

  expect(errors()).toEqual(browserName === "webkit" ? [] : [`pageerror: ${CANCELLED}`]);
});

test("cualquier otro error sigue contando, también en WebKit", async ({ page }) => {
  await page.goto("/login");
  const errors = watchBrowserErrors(page);
  const others = [
    "boom",
    "Fetch API cannot load http://localhost:3000/admin?_rsc=abc due to a network error.", // una precarga que falla por otra razón
    "Fetch API cannot load http://localhost:3000/api/me due to access control checks.", // el mismo motivo, pero no es una precarga RSC
  ];

  for (const message of others) await raise(page, message);
  const logged = page.waitForEvent("console", (message) => message.type() === "error");
  await page.evaluate((text) => console.error(text), CANCELLED); // como `console.error` tampoco se descarta
  await logged;

  expect(errors()).toEqual([...others.map((message) => `pageerror: ${message}`), `console.error: ${CANCELLED}`]);
});
