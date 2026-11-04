import path from "node:path";

import { test as base, expect, type BrowserContext, type Page } from "@playwright/test";

import { AUTH_DIR, type RoleKey } from "./env";

/** Falla la prueba si el navegador registra un `console.error` o una excepción de página (p. ej. un error de hidratación). */
function watchBrowserErrors(page: Page): string[] {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console.error: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  return problems;
}

type Fixtures = {
  /** Página ya autenticada como `role` con la sesión que guardó `auth.setup.ts` (mismo viewport y motor que el proyecto). */
  pageAs: (role: RoleKey) => Promise<Page>;
};

export const test = base.extend<Fixtures>({
  page: async ({ page }, use) => {
    const problems = watchBrowserErrors(page);
    await use(page);
    expect(problems, "el navegador registró errores").toEqual([]);
  },

  pageAs: async ({ browser }, use, testInfo) => {
    const engine = testInfo.project.name.split("-")[0];
    const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
    const contexts: BrowserContext[] = [];
    const watched: string[][] = [];

    await use(async (role) => {
      const context = await browser.newContext({
        baseURL,
        viewport,
        locale,
        timezoneId,
        storageState: path.join(AUTH_DIR, `${engine}-${role}.json`),
      });
      contexts.push(context);
      const page = await context.newPage();
      watched.push(watchBrowserErrors(page));
      return page;
    });

    await Promise.all(contexts.map((context) => context.close()));
    expect(watched.flat(), "el navegador registró errores").toEqual([]);
  },
});

export { expect };
