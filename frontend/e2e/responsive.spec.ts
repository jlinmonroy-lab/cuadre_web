// AC-14 · Interfaz adaptable y accesible, en los seis proyectos (Chromium, Firefox y WebKit; 390 y 1.440 px).
import { PEOPLE, type RoleKey } from "./helpers/env";
import { expect, test } from "./helpers/fixtures";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";

const NAV_BREAKPOINT = 901; // la barra lateral aparece desde 901 px; por debajo, barra superior (docs/cuadre-interfaz.html)

const ANONYMOUS_PAGES = ["/login", "/registro", "/recuperar"];
const SIGNED_IN_PAGES: [RoleKey, string][] = [
  ["alicia", "/inicio"],
  ["alicia", "/gastos"],
  ["alicia", "/403"],
  ["gina", "/cartera"],
  ["adan", "/admin"],
];

for (const path of ANONYMOUS_PAGES) {
  test(`responsive · ${path} sin sesión: sin scroll horizontal y con todos los campos etiquetados`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await expectEveryFieldLabelled(page);
  });
}

for (const [role, path] of SIGNED_IN_PAGES) {
  test(`responsive · ${path} como ${role}: sin scroll horizontal y con la barra en su sitio`, async ({ pageAs }, testInfo) => {
    const page = await pageAs(role);
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalScroll(page);

    const width = testInfo.project.use.viewport!.width;
    const aside = page.getByRole("complementary");
    const main = page.getByRole("main");
    const asideBox = (await aside.boundingBox())!;
    const mainBox = (await main.boundingBox())!;

    if (width < NAV_BREAKPOINT) {
      // Barra superior: ocupa todo el ancho, está arriba y el contenido va debajo.
      expect(asideBox.y).toBeLessThanOrEqual(1);
      expect(Math.round(asideBox.width)).toBe(width);
      expect(mainBox.y).toBeGreaterThanOrEqual(asideBox.y + asideBox.height - 1);
    } else {
      // Barra lateral de 232 px; el contenido a su derecha.
      expect(Math.round(asideBox.width)).toBe(232);
      expect(mainBox.x).toBeGreaterThanOrEqual(asideBox.x + asideBox.width - 1);
    }

    // «Cerrar sesión» siempre a la vista (en el prototipo se ocultaba en móvil; la spec exige poder cerrar sesión).
    await expect(page.getByRole("button", { name: "Cerrar sesión" })).toBeInViewport();
  });
}

test("responsive · la navegación del autónomo se desplaza dentro de la barra a 390 px y va en columna a 1.440 px", async ({ pageAs }, testInfo) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  const nav = page.getByRole("navigation", { name: "Apartados" });
  const items = nav.getByRole("listitem");
  await expect(items).toHaveCount(PEOPLE.alicia.nav.length);

  const overflows = await nav.evaluate((el) => el.scrollWidth > el.clientWidth);
  const first = (await items.nth(0).boundingBox())!;
  const second = (await items.nth(1).boundingBox())!;

  if (testInfo.project.use.viewport!.width < NAV_BREAKPOINT) {
    expect(overflows, "la navegación debe desbordar dentro de su barra, no en la página").toBe(true);
    expect(Math.abs(second.y - first.y), "los apartados van en una fila").toBeLessThan(2);
  } else {
    expect(overflows, "en la barra lateral nada se desplaza").toBe(false);
    expect(second.y, "los apartados van en columna").toBeGreaterThan(first.y);
    expect(Math.abs(second.x - first.x)).toBeLessThan(2);
  }
  await expectNoHorizontalScroll(page);
});

test("responsive · el foco se ve al tabular: el enlace de salto aparece y los campos y el botón cambian de estilo", async ({ page, browserName }) => {
  await page.goto("/login");
  const email = page.getByLabel("Correo electrónico");
  const password = page.getByLabel("Contraseña", { exact: true });
  const submit = page.getByRole("button", { name: "Entrar" });
  const skip = page.getByRole("link", { name: "Saltar al contenido" });

  // Firma del estilo que cambia con el foco, medida en reposo y con el foco puesto (independiente del motor).
  const signature = (locator: import("@playwright/test").Locator) =>
    locator.evaluate((el) => {
      const style = getComputedStyle(el);
      return [style.boxShadow, style.outlineStyle, style.outlineWidth, style.outlineColor, style.borderColor].join("|");
    });
  const resting = { email: await signature(email), password: await signature(password), submit: await signature(submit) };

  // Primer Tab: enlace «Saltar al contenido», oculto hasta recibir el foco. WebKit (como Safari) no detiene el Tab en los enlaces
  // salvo que el usuario lo active (Opción+Tab): allí solo se comprueban los controles de formulario.
  if (browserName === "webkit") {
    test.info().annotations.push({ type: "nota", description: "WebKit no tabula a los enlaces por defecto: no se comprueba el enlace de salto" });
  } else {
    await page.keyboard.press("Tab");
    await expect(skip).toBeFocused();
    expect((await skip.boundingBox())!.width, "el enlace de salto debe hacerse visible con el foco").toBeGreaterThan(40);
  }

  // Se avanza con Tab hasta cada control y se compara su estilo con el de reposo.
  const tabTo = async (target: import("@playwright/test").Locator) => {
    for (let presses = 0; presses < 8; presses++) {
      if (await target.evaluate((el) => el === document.activeElement)) return;
      await page.keyboard.press("Tab");
    }
    await expect(target).toBeFocused();
  };
  await tabTo(email);
  expect(await signature(email), "el campo de correo no muestra el foco").not.toBe(resting.email);
  await tabTo(password);
  expect(await signature(password), "el campo de contraseña no muestra el foco").not.toBe(resting.password);
  await tabTo(submit);
  expect(await signature(submit), "el botón no muestra el foco").not.toBe(resting.submit);
});
