import path from "node:path";

import { test as base, expect, type BrowserContext, type Page } from "@playwright/test";

import { API_URL, AUTH_DIR, type RoleKey } from "./env";
import { Ledger } from "./ledger";
import { signUpAndConfirm, uniqueEmail } from "./session";

/** Falla la prueba si el navegador registra un `console.error` o una excepción de página (p. ej. un error de hidratación). */
function watchBrowserErrors(page: Page): string[] {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console.error: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  return problems;
}

/**
 * Espera, sin fallar, a que la página no tenga peticiones en vuelo. Navegar o cerrar una página con una petición RSC a medias (la
 * precarga de un enlace, un `router.refresh()`) hace que Firefox y WebKit registren un error de red, sin que haya ningún fallo: antes de
 * moverse o de cerrar, las pruebas dejan que la página se calme.
 */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => undefined);
}

/** Cierra un contexto sin que un error del protocolo de Firefox al cerrarlo (`Browser.removeBrowserContext`) tumbe una prueba que ya acabó. */
async function closeQuietly(context: BrowserContext): Promise<void> {
  await context.close().catch(() => undefined);
}

type StorageState = Awaited<ReturnType<BrowserContext["storageState"]>>;

type Fixtures = {
  /** Página ya autenticada como `role` con la sesión que guardó `auth.setup.ts` (mismo viewport y motor que el proyecto). */
  pageAs: (role: RoleKey) => Promise<Page>;
  /** Página con la sesión de `gastosUser` (misma cuenta durante todo el worker; mismo viewport y motor que el proyecto). */
  gastosPage: Page;
  /**
   * El libro de gastos de `gastosUser` por la API: `seed` crea gastos y, al terminar la prueba, **todos los gastos vivos de la cuenta se
   * anulan**. La cuenta es la del worker y varias pruebas registran la misma factura de ejemplo; sin esta limpieza un gasto que quedase
   * vivo (o una prueba que falla a mitad) haría fallar «No está registrada ya» en la siguiente.
   */
  ledger: Ledger;
};

type WorkerFixtures = {
  /**
   * Una cuenta de `usuario` **nueva por worker**, creada por el propio formulario de registro. Gastos limita a 5 las lecturas
   * simultáneas por persona (AC-12) y la lista de documentos es de la cuenta: compartir a Alicia entre seis proyectos en paralelo
   * daría 429 y listas ajenas. Las pruebas buscan su documento por un nombre de archivo único.
   */
  gastosUser: { email: string; storageState: StorageState };
};

export const test = base.extend<Fixtures, WorkerFixtures>({
  gastosUser: [
    async ({ browser }, use, workerInfo) => {
      const { baseURL, viewport, locale, timezoneId } = workerInfo.project.use;
      const context = await browser.newContext({ baseURL, viewport, locale, timezoneId });
      const email = uniqueEmail(`gastos-${workerInfo.project.name}`);
      await signUpAndConfirm(await context.newPage(), { name: "Gastos E2E", email });
      const storageState = await context.storageState();
      await closeQuietly(context);
      await use({ email, storageState });
    },
    { scope: "worker", timeout: 90_000 },
  ],

  gastosPage: async ({ browser, gastosUser }, use, testInfo) => {
    const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
    const context = await browser.newContext({ baseURL, viewport, locale, timezoneId, storageState: gastosUser.storageState });
    const page = await context.newPage();
    const problems = watchBrowserErrors(page);
    await use(page);
    await settle(page);
    const found = [...problems]; // lo que provoque el cierre no cuenta
    await closeQuietly(context);
    expect(found, "el navegador registró errores").toEqual([]);
  },

  ledger: async ({ request, gastosUser }, use) => {
    const ledger = new Ledger(request, gastosUser.email, API_URL);
    await use(ledger);
    await ledger.voidAll();
  },

  page: async ({ page }, use) => {
    const problems = watchBrowserErrors(page);
    await use(page);
    await settle(page);
    expect(problems, "el navegador registró errores").toEqual([]);
  },

  pageAs: async ({ browser }, use, testInfo) => {
    const engine = testInfo.project.name.split("-")[0];
    const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
    const contexts: BrowserContext[] = [];
    const pages: Page[] = [];
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
      pages.push(page);
      watched.push(watchBrowserErrors(page));
      return page;
    });

    await Promise.all(pages.map(settle));
    const found = watched.flat(); // lo que provoque el cierre no cuenta
    await Promise.all(contexts.map(closeQuietly));
    expect(found, "el navegador registró errores").toEqual([]);
  },
});

export { expect };
