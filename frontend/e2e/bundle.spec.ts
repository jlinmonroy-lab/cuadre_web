// AC-15 (parte del navegador) · Lo que `next start` sirve de verdad no contiene la clave de servicio ni las URL de la base de datos.
// Complementa a `npm run check:bundle`, que revisa los ficheros de .next; esta prueba revisa lo que llega por la red. Solo en chromium-1440.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

import { STATIC_NEEDLES, collectNeedles } from "../scripts/bundle-scan.mjs";
import { expect, test } from "./helpers/fixtures";

const ROOT_ENV = path.join(__dirname, "..", "..", ".env");
const SERVED_TYPES = new Set(["document", "script", "stylesheet", "fetch", "xhr"]);

/** Guarda los cuerpos de texto que sirve el servidor mientras se navega por `pages`. */
function collectServedBodies(page: Page): { url: string; text: string }[] {
  const bodies: { url: string; text: string }[] = [];
  page.on("response", async (response) => {
    if (!SERVED_TYPES.has(response.request().resourceType())) return;
    try {
      bodies.push({ url: response.url(), text: await response.text() });
    } catch {
      // redirecciones y respuestas sin cuerpo
    }
  });
  return bodies;
}

function leaks(bodies: { url: string; text: string }[]): string[] {
  const envText = existsSync(ROOT_ENV) ? readFileSync(ROOT_ENV, "utf8") : "";
  const needles = [...STATIC_NEEDLES, ...collectNeedles(envText, process.env)];
  return bodies.flatMap(({ url, text }) =>
    needles
      .filter((needle) => ("pattern" in needle && needle.pattern ? needle.pattern.test(text) : "value" in needle && needle.value && text.includes(needle.value)))
      .map((needle) => `${url} contiene ${needle.label}`),
  );
}

test("bundle · lo que recibe el navegador sin sesión no contiene secretos del servidor", async ({ page }) => {
  const bodies = collectServedBodies(page);
  for (const path of ["/login", "/registro", "/recuperar"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
  }
  expect(bodies.filter((body) => body.url.includes("/_next/static/")).length, "la prueba debe ver los scripts del cliente").toBeGreaterThan(3);
  expect(leaks(bodies)).toEqual([]);
});

test("bundle · lo que recibe el navegador con sesión (HTML, flujo RSC y scripts) tampoco", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  const bodies = collectServedBodies(page);
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Hola, Alicia");
  await page.getByRole("link", { name: "Inicio", exact: true }).first().click();
  await page.goto("/403");
  await page.waitForLoadState("networkidle");
  expect(bodies.length).toBeGreaterThan(3);
  expect(leaks(bodies)).toEqual([]);
});
