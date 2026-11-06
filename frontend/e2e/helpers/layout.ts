// Comprobaciones de maquetación y accesibilidad que comparten `responsive.spec.ts` y `gastos-subida.spec.ts` (T2-11, AC-10).
import { expect, type Page } from "@playwright/test";

/** El documento no puede ser más ancho que la ventana: nada obliga a hacer scroll horizontal. */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(scrollWidth, "la anchura del documento no puede superar la de la ventana").toBeLessThanOrEqual(innerWidth);
}

/** Todo campo de formulario visible tiene una etiqueta asociada. */
export async function expectEveryFieldLabelled(page: Page): Promise<void> {
  const unlabelled = await page
    .locator("input:not([type=hidden]), select, textarea")
    .evaluateAll((fields) => fields.filter((field) => !(field as HTMLInputElement).labels?.length).map((field) => field.id || field.getAttribute("name")));
  expect(unlabelled, "campos sin etiqueta asociada").toEqual([]);
}
