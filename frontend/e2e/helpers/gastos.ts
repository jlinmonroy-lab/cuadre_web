// Lo que comparten las pruebas de Gastos (`gastos-subida.spec.ts` y `gastos-registro.spec.ts`): subir, abrir la revisión y localizar.
//
// Ojo con los localizadores: con `cacheComponents`, Next 16 conserva **ocultas** las pantallas por las que se ha navegado (`<Activity>`), así
// que tras pulsar un enlace la lista de Gastos sigue en el DOM con su texto y sus ids; y la lista de gastos registrados lleva tarjetas y
// tabla a la vez, una con `display: none`. `getByRole` ignora lo oculto; `getByText`, `getByLabel` y los selectores CSS no, y por eso pasan
// por `shown`.
import type { Locator, Page } from "@playwright/test";

import { expect, settle } from "./fixtures";
import type { UploadFile } from "./files";

export const DOCUMENT_URL = /\/gastos\/[0-9a-f-]{36}$/;
export const READY = "Listo: ya puedes revisarlo.";
export const FAILED = "No se ha podido leer.";
export const READING_TIMEOUT = 30_000;

export const shown = (locator: Locator): Locator => locator.filter({ visible: true });
export const text = (page: Page, value: string | RegExp): Locator => shown(page.getByText(value));
/** La fila de la zona de subida (la de este archivo), no la tarjeta de la lista. */
export const uploadRow = (page: Page, file: UploadFile): Locator => shown(page.locator("[aria-live=polite] li")).filter({ hasText: file.name });
/** La tarjeta de la lista de documentos. */
export const card = (page: Page, file: UploadFile): Locator => page.getByRole("article").filter({ hasText: file.name });
export const idFrom = (page: Page): string => new URL(page.url()).pathname.split("/").pop() ?? "";
export const field = (page: Page, label: string): Locator => shown(page.getByLabel(label, { exact: true }));
export const registerButton = (page: Page): Locator => page.getByRole("button", { name: "Registrar gasto" });
export const savedMessage = (page: Page): Locator => page.getByRole("status").filter({ hasText: "Cambios guardados." });

export async function openGastos(page: Page): Promise<void> {
  await settle(page); // no se navega con una petición RSC a medias (ver `settle`)
  await page.goto("/gastos");
  await expect(page.getByRole("heading", { level: 1, name: "Gastos" })).toBeVisible();
}

/** Sube los archivos por «Elegir archivos» y espera a que cada uno termine (bien o mal: qué se esperaba lo comprueba cada prueba). */
export async function upload(page: Page, ...files: UploadFile[]): Promise<void> {
  await page.locator("#gastos-archivos").setInputFiles(files);
  for (const file of files) {
    await expect(uploadRow(page, file).getByText(new RegExp(`${READY}|${FAILED}`.replaceAll(".", "\\.")))).toBeVisible({ timeout: READING_TIMEOUT });
  }
}

/** Sube un archivo, espera a que termine y abre su pantalla de revisión. */
export async function uploadAndOpen(page: Page, file: UploadFile): Promise<string> {
  await openGastos(page);
  await upload(page, file);
  await uploadRow(page, file).getByRole("link", { name: /^(Revisar|Abrir)$/ }).click();
  await expect(page).toHaveURL(DOCUMENT_URL);
  await expect(page.getByRole("heading", { level: 1, name: file.name })).toBeVisible();
  return idFrom(page);
}

/**
 * Espera a que React acabe de asentar un formulario tras una acción del servidor. Con `<form action>`, React 19 pinta primero el resultado
 * (el mensaje de error) y reinicia los campos sin controlar en un commit posterior, a unos milisegundos: un `fill` justo después del error
 * puede perderse (WebKit lo hacía 1 de cada 40 veces; ninguna persona escribe en esa ventana). Dos fotogramas bastan para que ese commit ya
 * haya pasado.
 */
export async function settleForm(page: Page): Promise<void> {
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}
