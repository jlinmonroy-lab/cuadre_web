import { randomUUID } from "node:crypto";
import path from "node:path";

import { test as base, expect, type BrowserContext, type Page } from "@playwright/test";

import { ClientsApi, type ListedClient } from "./clients";
import { API_URL, AUTH_DIR, FIRST_PASSWORD, GUS, PEOPLE, SEED_PASSWORD, type RoleKey } from "./env";
import { GestorApi } from "./gestor";
import { InvoicesApi } from "./invoices";
import { Ledger } from "./ledger";
import { ProfileApi } from "./profile";
import { TaxApi } from "./tax";
import { signUpAndConfirm, uniqueEmail } from "./session";

/**
 * WebKit cuenta como excepción de página la precarga RSC (`?_rsc=`, la de un `<Link>`) que una navegación dura cancela a medias:
 * «Fetch API cannot load …?_rsc=… due to access control checks.». No es un fallo de la aplicación: la misma petición sale como
 * `requestfailed` con «Load request cancelled». En el primer CI (SPEC-W-003 B.7) ocurrió aunque la prueba esperase a `settle`, porque
 * `networkidle` es una heurística y Next puede lanzar una precarga después de su ventana. Se descarta ese mensaje exacto, solo en WebKit y
 * solo como excepción de página; cualquier otro error sigue contando (`browser-errors.spec.ts` fija los dos lados).
 */
const CANCELLED_PREFETCH = /^pageerror: .*[?&]_rsc=[\w-]+ due to access control checks\.$/;

/** ` (en /ruta)` de la URL de un mensaje de consola, sin query ni dominio; vacío si no hay URL. */
function locationOf(url: string): string {
  try {
    return url ? ` (en ${new URL(url).pathname})` : "";
  } catch {
    return "";
  }
}

/**
 * Vigila al navegador: devuelve una función que da los errores vistos hasta ahora, un `console.error` o una excepción de página (p. ej. un
 * error de hidratación) salvo la precarga RSC cancelada de arriba. Las pruebas fallan si no está vacía.
 */
export function watchBrowserErrors(page: Page): () => string[] {
  const problems: string[] = [];
  page.on("console", async (message) => {
    if (message.type() !== "error") return;
    // Firefox y WebKit escriben «JSHandle@object» cuando se registra un objeto (p. ej. un `Error`): se lee su texto para poder diagnosticarlo en el CI.
    let text = message.text();
    if (text.includes("JSHandle@")) {
      const described = await Promise.all(
        message.args().map((handle) =>
          handle
            .evaluate((value: unknown) => {
              const error = value as { name?: unknown; message?: unknown; stack?: unknown } | null;
              return error && typeof error === "object" && "message" in error ? `${String(error.name)}: ${String(error.message)}` : String(value);
            })
            .catch(() => "?"),
        ),
      );
      text = described.join(" ");
    }
    // Un «Failed to load resource» no dice qué recurso era: se añade la ruta (sin query ni dominio) para poder diagnosticarlo en el CI.
    problems.push(`console.error: ${text}${locationOf(message.location().url)}`);
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  const webkit = page.context().browser()?.browserType().name() === "webkit";
  return () => (webkit ? problems.filter((problem) => !CANCELLED_PREFETCH.test(problem)) : [...problems]);
}

/**
 * Espera, sin fallar, a que la página no tenga peticiones en vuelo. Navegar o cerrar una página con una petición RSC a medias (la
 * precarga de un enlace, un `router.refresh()`) hace que Firefox y WebKit registren un error de red, sin que haya ningún fallo: antes de
 * moverse o de cerrar, las pruebas dejan que la página se calme. Reduce la carrera, no la cierra (ver `CANCELLED_PREFETCH`).
 */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => undefined);
}

/** Cierra un contexto sin que un error del protocolo de Firefox al cerrarlo (`Browser.removeBrowserContext`) tumbe una prueba que ya acabó. */
async function closeQuietly(context: BrowserContext): Promise<void> {
  await context.close().catch(() => undefined);
}

type StorageState = Awaited<ReturnType<BrowserContext["storageState"]>>;

/** NIF, domicilio y retención sintéticos con los que `biller` deja completo el perfil de la cuenta del worker. */
export const BILLER_PROFILE = {
  legal_name: "Facturación E2E, diseño gráfico",
  tax_id: "12345678Z",
  fiscal_address: "Calle Ficticia 1, 28001 Madrid",
  irpf_rate: "15.00",
};

/** Un cliente de cada tratamiento fiscal, más uno sin domicilio (NIF y NIF-IVA sintéticos con dígitos de control válidos). */
export type BillerClients = {
  national: ListedClient; // empresa en España: IVA 21 % y retención
  euBusiness: ListedClient; // empresa de Alemania: inversión del sujeto pasivo
  euPerson: ListedClient; // particular de Alemania: IVA español
  usPerson: ListedClient; // particular de EE. UU.: IVA español
  mxBusiness: ListedClient; // empresa de México: no sujeta (art. 69)
  noAddress: ListedClient; // empresa en España sin domicilio: no se puede facturar
};

export type Biller = { clients: BillerClients; invoices: InvoicesApi; profile: ProfileApi; clientsApi: ClientsApi };

type Fixtures = {
  /** Página ya autenticada como `role` con la sesión que guardó `auth.setup.ts` (mismo viewport y motor que el proyecto). */
  pageAs: (role: RoleKey) => Promise<Page>;
  /**
   * Errores de navegador que ESTA prueba provoca a propósito (p. ej. un 503 que el agente de E2E devuelve para probar «Reintentar»: Chromium lo
   * apunta como `console.error`). `gastosPage` los descarta al final; cualquier otro sigue haciendo fallar la prueba. Cada patrón se compara con
   * el texto completo que registra `watchBrowserErrors` y debe ser lo bastante concreto para no esconder otra cosa.
   */
  expectedBrowserErrors: RegExp[];
  /** Página con la sesión de `gastosUser` (misma cuenta durante todo el worker; mismo viewport y motor que el proyecto). */
  gastosPage: Page;
  /**
   * El libro de gastos de `gastosUser` por la API: `seed` crea gastos y, al terminar la prueba, **todos los gastos vivos de la cuenta se
   * anulan**. La cuenta es la del worker y varias pruebas registran la misma factura de ejemplo; sin esta limpieza un gasto que quedase
   * vivo (o una prueba que falla a mitad) haría fallar «No está registrada ya» en la siguiente.
   */
  ledger: Ledger;
  /**
   * El perfil de `gastosUser` por la API: se **restaura al empezar y al terminar** (vacío, sin logo y solo la serie del año). Las pruebas de
   * Gastos esperan un perfil vacío y la cuenta es la del worker, así que toda prueba que escriba el perfil debe usar este fixture (T5-11).
   */
  profile: ProfileApi;
  /**
   * Los clientes de `gastosUser` por la API: se **archivan todos al empezar y al terminar** (T6-10). Un cliente no se borra y el NIF es único
   * entre los activos de cada persona, así que ninguna prueba puede depender de lo que dejó otra en la cuenta del worker.
   */
  clients: ClientsApi;
  /**
   * La cuenta de `gastosUser` lista para FACTURAR (SPEC-W-007 hito 6): perfil completo con retención del 15 %, un cliente de cada tratamiento y uno sin
   * domicilio, y un ayudante para emitir por la API. Al terminar, `profile` restaura el perfil vacío y `clients` archiva los clientes; las facturas
   * emitidas NO se pueden borrar (RES-03, T7-13): quedan en la cuenta y ninguna prueba cuenta filas ni números absolutos.
   */
  biller: Biller;
  /** El borrador del 303 de `gastosUser` por la API: el oráculo de `trimestres.spec.ts` (solo lee). */
  tax: TaxApi;
  /**
   * El acceso del gestor de `gastosUser` por la API (SPEC-W-010): `owner` es la cuenta, `gina` y `gus` los dos gestores del seed. **Revoca todo lo abierto de la
   * cuenta al empezar y al terminar**: la gestora es compartida entre workers y proyectos y la cuenta admite 5 invitaciones abiertas (T10-12).
   */
  gestor: { owner: GestorApi; gina: GestorApi; gus: GestorApi };
};

type WorkerFixtures = {
  /**
   * Una cuenta de `usuario` **nueva por worker**, creada por el propio formulario de registro. Gastos limita a 5 las lecturas
   * simultáneas por persona (AC-12) y la lista de documentos es de la cuenta: compartir a Alicia entre seis proyectos en paralelo
   * daría 429 y listas ajenas. Las pruebas buscan su documento por un nombre de archivo único.
   */
  gastosUser: { email: string; /** Nombre único por worker: la gestora compartida lo usa para encontrar a SU autónomo en la cartera. */ name: string; storageState: StorageState };
};

export const test = base.extend<Fixtures, WorkerFixtures>({
  gastosUser: [
    async ({ browser }, use, workerInfo) => {
      const { baseURL, viewport, locale, timezoneId } = workerInfo.project.use;
      const context = await browser.newContext({ baseURL, viewport, locale, timezoneId });
      const email = uniqueEmail(`gastos-${workerInfo.project.name}`);
      const name = `Gastos ${randomUUID().slice(0, 8)}`;
      await signUpAndConfirm(await context.newPage(), { name, email });
      const storageState = await context.storageState();
      await closeQuietly(context);
      await use({ email, name, storageState });
    },
    { scope: "worker", timeout: 90_000 },
  ],

  expectedBrowserErrors: async ({}, use) => {
    await use([]);
  },

  gastosPage: async ({ browser, gastosUser, expectedBrowserErrors }, use, testInfo) => {
    const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
    const context = await browser.newContext({ baseURL, viewport, locale, timezoneId, storageState: gastosUser.storageState });
    const page = await context.newPage();
    const errors = watchBrowserErrors(page);
    await use(page);
    await settle(page);
    const found = errors().filter((problem) => !expectedBrowserErrors.some((expected) => expected.test(problem))); // lo que provoque el cierre no cuenta
    await closeQuietly(context);
    expect(found, "el navegador registró errores").toEqual([]);
  },

  ledger: async ({ request, gastosUser }, use) => {
    const ledger = new Ledger(request, gastosUser.email, API_URL);
    await use(ledger);
    await ledger.voidAll();
  },

  profile: async ({ request, gastosUser }, use) => {
    const profile = new ProfileApi(request, gastosUser.email, API_URL);
    await profile.restore();
    await use(profile);
    await profile.restore();
  },

  clients: async ({ request, gastosUser }, use) => {
    const clients = new ClientsApi(request, gastosUser.email, API_URL);
    await clients.archiveAll();
    await use(clients);
    await clients.archiveAll();
  },

  biller: async ({ profile, clients, request, gastosUser }, use) => {
    await profile.save(BILLER_PROFILE);
    const make = (input: Parameters<ClientsApi["create"]>[0]) => clients.create(input);
    const created: BillerClients = {
      national: await make({ name: "Estudio Norte S.L.", kind: "business", country: "ES", tax_id: "B00000018", address: "Avenida Inventada 4, 28000 Madrid" }),
      euBusiness: await make({ name: "Kreativ GmbH", kind: "business", country: "DE", tax_id: "DE534861408", address: "Beispielstrasse 1, 10115 Berlin" }),
      euPerson: await make({ name: "Lena Müller", kind: "individual", country: "DE", address: "Musterweg 3, 80331 München" }),
      usPerson: await make({ name: "Jane Doe", kind: "individual", country: "US", address: "1 Main Street, Springfield" }),
      mxBusiness: await make({ name: "Taller Zócalo", kind: "business", country: "MX", tax_id: "XAXX010101000", address: "Calle Ejemplo 5, Ciudad de México" }),
      noAddress: await make({ name: "Sin Domicilio S.L.", kind: "business", country: "ES", tax_id: "B00000026" }),
    };
    await use({ clients: created, invoices: new InvoicesApi(request, gastosUser.email, API_URL), profile, clientsApi: clients });
  },

  tax: async ({ request, gastosUser }, use) => {
    await use(new TaxApi(request, gastosUser.email, API_URL));
  },

  gestor: async ({ request, gastosUser }, use) => {
    const owner = new GestorApi(request, gastosUser.email, FIRST_PASSWORD, API_URL);
    await owner.revokeOpen();
    await use({
      owner,
      gina: new GestorApi(request, PEOPLE.gina.email, SEED_PASSWORD, API_URL),
      gus: new GestorApi(request, GUS.email, SEED_PASSWORD, API_URL),
    });
    await owner.revokeOpen();
  },

  page: async ({ page }, use) => {
    const errors = watchBrowserErrors(page);
    await use(page);
    await settle(page);
    expect(errors(), "el navegador registró errores").toEqual([]);
  },

  pageAs: async ({ browser }, use, testInfo) => {
    const engine = testInfo.project.name.split("-")[0];
    const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
    const contexts: BrowserContext[] = [];
    const pages: Page[] = [];
    const watched: Array<() => string[]> = [];

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
    const found = watched.flatMap((errors) => errors()); // lo que provoque el cierre no cuenta
    await Promise.all(contexts.map(closeQuietly));
    expect(found, "el navegador registró errores").toEqual([]);
  },
});

export { expect };
