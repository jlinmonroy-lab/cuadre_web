// Lo que comparten las pruebas del asistente (`chat.spec.ts`): marcadores para el agente de E2E, abrir la pantalla, enviar y localizar.
//
// Los textos están escritos a mano, no importados de `src/lib/chat.ts`: son el oráculo. Si alguien cambia un texto de la aplicación, estas pruebas
// deben avisar. Ojo con los localizadores (ver `gastos.ts`): con `cacheComponents` Next 16 deja ocultas las pantallas visitadas, y la lista de
// conversaciones va dos veces (la columna y el `<details>` del móvil), así que lo que no sea `getByRole` pasa por `shown`.
import { randomUUID } from "node:crypto";

import type { Locator, Page } from "@playwright/test";

import { expect, settle } from "./fixtures";
import { shown } from "./gastos";

export const NOTICE = "Cuadre orienta, no asesora. Para decidir sobre tu caso, consulta a tu gestor o a un asesor.";
export const EMPTY_THREAD = "Aún no has preguntado nada. Escribe tu duda abajo y te respondo con fuentes oficiales.";
export const NO_SOURCE_NOTE = "Esta respuesta no cita ninguna fuente oficial: tómala solo como orientación.";
export const INTERRUPTED_NOTE = "Respuesta interrumpida: esto es lo que llegó antes de cortarse.";
export const UNAVAILABLE = "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.";
export const GENERIC_ERROR = "El asistente no ha podido terminar la respuesta.";
export const MISSING = "No encontramos esa conversación. Puedes empezar una nueva o abrir otra de la lista.";

/** El primer y el segundo trozo de `answer_with_citation`, por separado: el segundo no puede verse antes de tiempo. */
export const CITATION_FIRST = "Si el cliente es una empresa de la UE con NIF-IVA válido,";
export const CITATION_SECOND = "debe incluir la mención «Inversión del sujeto pasivo» [1].";
export const CITATION_TITLE = "Real Decreto 1619/2012, Reglamento por el que se regulan las obligaciones de facturación";
export const CITATION_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696";
/** El primer trozo de `answer_length`. */
export const LENGTH_FIRST = "La factura simplificada solo puede emitirse en los casos que fija el reglamento:";

export type Script = {
  fixture: string;
  /** Desde la 2.ª petición de esa conversación se sirve este (para «Reintentar»). */
  then?: string;
  /** Milisegundos de pausa antes de cada frame (el agente de E2E los acota a 5 s). */
  pace?: number;
};

/** Una etiqueta única por prueba: el título de la conversación sale de la primera pregunta y la cuenta es la del worker. */
export const newTag = (): string => randomUUID().slice(0, 8);

/** El texto que se escribe: la etiqueta y los marcadores que leerá el agente de E2E (`backend/tests/agents/e2e_server.py`). */
export function question(tag: string, script: Script): string {
  return `Pregunta ${tag} [fixture:${script.fixture}]${script.then ? `[then:${script.then}]` : ""}${script.pace ? `[pace=${script.pace}]` : ""}`;
}

export const field = (page: Page): Locator => shown(page.getByLabel("Tu pregunta", { exact: true }));
export const sendButton = (page: Page): Locator => page.getByRole("button", { name: "Enviar", exact: true });
export const stopButton = (page: Page): Locator => page.getByRole("button", { name: "Detener", exact: true });
/** Los mensajes del hilo: `article` con nombre «Tú» o «Asistente». */
export const mine = (page: Page): Locator => page.getByRole("article", { name: "Tú", exact: true });
export const replies = (page: Page): Locator => page.getByRole("article", { name: "Asistente", exact: true });
/** El hilo entero: `aria-busy` es `true` mientras se espera o llega una respuesta. */
export const thread = (page: Page): Locator => page.getByRole("region", { name: "Conversación con el asistente" });
export const notices = (page: Page): Locator => shown(page.getByText(NOTICE, { exact: true }));
export const alerts = (container: Locator | Page, text: string): Locator => container.getByRole("alert").filter({ hasText: text });

export async function openAssistant(page: Page): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto("/asistente");
  await expect(page.getByRole("heading", { level: 1, name: "Asistente", exact: true })).toBeVisible();
  await expect(field(page)).toBeVisible();
  await hydrated(page);
}

/**
 * Espera a que React haya hidratado el campo. El HTML del servidor ya trae el `<textarea>`, y un `fill` antes de la hidratación se pierde (React lo
 * vuelve a poner en blanco, el botón sigue desactivado: WebKit lo hacía casi siempre). Ninguna persona escribe en esa ventana. Se sabe que está
 * hidratado cuando el contador, que depende del estado de React, sigue lo que se escribe.
 */
async function hydrated(page: Page): Promise<void> {
  await expect(async () => {
    await field(page).fill(""); // si ya está en «x», un segundo `fill("x")` no cambia nada y React no se entera
    await field(page).fill("x");
    await expect(shown(page.getByText(/^1 de 2000 caracteres/))).toBeVisible({ timeout: 500 });
  }).toPass({ timeout: 15_000 });
  await field(page).fill("");
  await expect(shown(page.getByText(/^0 de 2000 caracteres/))).toBeVisible();
}

/** Recarga sin una petición RSC a medias (el `router.refresh()` que sigue a cada respuesta): Firefox y WebKit la cuentan como error de red (ver `settle`). */
export async function reload(page: Page): Promise<void> {
  await settle(page);
  await page.waitForTimeout(500); // `networkidle` no ve una petición que Next aún no ha lanzado (precarga de un enlace, refresco): se mira otra vez
  await settle(page);
  await page.reload();
}

/** Escribe y pulsa «Enviar». */
export async function send(page: Page, text: string): Promise<void> {
  await field(page).fill(text);
  await sendButton(page).click();
}

/** Espera a que no haya respuesta en curso: el hilo ya no está ocupado y vuelve «Enviar». */
export async function finished(page: Page): Promise<void> {
  await expect(thread(page)).toHaveAttribute("aria-busy", "false");
  await expect(sendButton(page)).toBeVisible();
}

/** Tras el primer mensaje de una conversación nueva la dirección pasa a `?c=<uuid>`: devuelve ese id. */
export async function conversationId(page: Page): Promise<string> {
  await expect(page).toHaveURL(/\/asistente\?c=[0-9a-f-]{36}$/);
  return new URL(page.url()).searchParams.get("c") ?? "";
}

/** En el móvil la lista está en un `<details>` cerrado: se abre. Desde 901 px es una columna y no hace falta. */
export async function openList(page: Page): Promise<void> {
  const details = page.locator("details", { has: page.locator('nav[aria-label="Tus conversaciones"]') });
  if ((await details.isVisible()) && !(await details.evaluate((element: HTMLDetailsElement) => element.open))) {
    await details.locator("summary").click();
  }
}

export const conversationLink = (page: Page, tag: string): Locator =>
  page.getByRole("navigation", { name: "Tus conversaciones" }).getByRole("link").filter({ hasText: tag });

/** Abre la conversación de esta etiqueta desde la lista. */
export async function openConversation(page: Page, tag: string): Promise<void> {
  await openList(page);
  await conversationLink(page, tag).click();
  await expect(page).toHaveURL(/\/asistente\?c=[0-9a-f-]{36}$/);
}
