// AC-01 registro · AC-03 recuperación · AC-04 sin sesión · inicio y cierre de sesión (SPEC-W-001 §5.3 y §7).
// La parte de base de datos de AC-01 (perfil, ficha de negocio y registro de actividad) la cubre backend/tests/rls/test_signup_trigger.py.
import { API_URL, FIRST_PASSWORD, PEOPLE, SECOND_PASSWORD, SEED_PASSWORD, WEB_URL } from "./helpers/env";
import { expect, test } from "./helpers/fixtures";
import { countMessagesTo, waitForLink } from "./helpers/mailpit";
import { expectNavigation, fillLogin, formAlert, login, signUpAndConfirm, uniqueEmail } from "./helpers/session";

const WRONG_CREDENTIALS = "Correo o contraseña incorrectos.";
const RECOVERY_SENT = "Si existe una cuenta con ese correo, te hemos enviado un enlace para elegir una contraseña nueva.";

// --- AC-01 · registro ------------------------------------------------------------------------------------------------------------

test("registro · los errores salen junto al campo, con un resumen que recibe el foco", async ({ page }) => {
  await page.goto("/registro");
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  const summary = formAlert(page);
  await expect(summary).toBeFocused();
  await expect(summary).toContainText("Escribe tu nombre.");
  await expect(summary).toContainText("Escribe tu correo.");
  await expect(summary).toContainText("Escribe una contraseña.");
  await expect(page.getByLabel("Nombre")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Correo electrónico")).toHaveAttribute("aria-invalid", "true");

  // Contraseña corta: el error sale junto al campo, y nombre y correo se conservan, pero la contraseña no vuelve al navegador.
  await page.getByLabel("Nombre").fill("Lucía E2E");
  await page.getByLabel("Correo electrónico").fill("corta@example.test");
  await page.getByLabel("Contraseña", { exact: true }).fill("corta");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(formAlert(page)).toContainText("La contraseña debe tener al menos 10 caracteres.");
  await expect(page.getByLabel("Contraseña", { exact: true })).toHaveAttribute("aria-describedby", /signup-password-error/);
  await expect(page.getByLabel("Nombre")).toHaveValue("Lucía E2E");
  await expect(page.getByLabel("Correo electrónico")).toHaveValue("corta@example.test");
  await expect(page.getByLabel("Contraseña", { exact: true })).toHaveValue("");
});

test("registro · cuenta nueva: confirma el enlace del correo y aterriza en /inicio", async ({ page, browserName }) => {
  const email = uniqueEmail(browserName);
  await page.goto("/registro");
  await page.getByLabel("Nombre").fill("Lucía E2E");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(FIRST_PASSWORD);
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Te hemos enviado un correo para confirmar tu cuenta. Abre el enlace que contiene y después inicia sesión.",
  );

  // Sin confirmar todavía no se entra, y el mensaje no delata el motivo (spec §5.3).
  await login(page, email, FIRST_PASSWORD);
  await expect(formAlert(page)).toHaveText(WRONG_CREDENTIALS);

  await page.goto((await waitForLink(email, "email")).toString());
  await expect(page).toHaveURL("/inicio");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Hola, Lucía");
  await expectNavigation(page, PEOPLE.alicia);
});

// --- AC-03 · recuperación de contraseña ------------------------------------------------------------------------------------------

test("recuperación · restablecer la contraseña con el enlace del correo", async ({ page, browserName }) => {
  const email = uniqueEmail(browserName);
  const unknown = uniqueEmail(`${browserName}-sin-cuenta`);
  await signUpAndConfirm(page, { name: "Recupera E2E", email });
  await page.context().clearCookies(); // ahora es una persona sin sesión que ha olvidado la contraseña

  // El mismo mensaje exista o no la cuenta.
  const sentMessages: string[] = [];
  for (const address of [unknown, email]) {
    await page.goto("/recuperar");
    await page.getByLabel("Correo electrónico").fill(address);
    await page.getByRole("button", { name: "Enviar enlace" }).click();
    await expect(page.getByRole("status")).toContainText(RECOVERY_SENT);
    sentMessages.push((await page.getByRole("status").innerText()).trim());
  }
  expect(sentMessages[0]).toBe(sentMessages[1]);

  // El correo llega a la cuenta real; a la inexistente no llegó ninguno (ya llegó el de la real, que se pidió después).
  const link = await waitForLink(email, "recovery");
  expect(await countMessagesTo(unknown)).toBe(0);

  await page.goto(link.toString());
  await expect(page).toHaveURL("/restablecer");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Elige una contraseña nueva");

  const newPassword = page.getByLabel("Contraseña nueva", { exact: true });
  const confirm = page.getByLabel("Repite la contraseña nueva");
  const save = page.getByRole("button", { name: "Guardar contraseña" });

  await newPassword.fill(SECOND_PASSWORD);
  await confirm.fill(`${SECOND_PASSWORD}-distinta`);
  await save.click();
  await expect(formAlert(page)).toContainText("Las contraseñas no coinciden.");

  await newPassword.fill(FIRST_PASSWORD); // la de siempre
  await confirm.fill(FIRST_PASSWORD);
  await save.click();
  await expect(formAlert(page)).toContainText("Elige una contraseña distinta de la anterior.");

  await newPassword.fill(SECOND_PASSWORD);
  await confirm.fill(SECOND_PASSWORD);
  await save.click();
  await expect(page).toHaveURL("/login?aviso=restablecida");
  await expect(page.getByRole("status")).toHaveText("Contraseña actualizada. Ya puedes iniciar sesión.");

  // La antigua ya no entra; la nueva, sí.
  await fillLogin(page, email, FIRST_PASSWORD);
  await expect(formAlert(page)).toHaveText(WRONG_CREDENTIALS);
  await fillLogin(page, email, SECOND_PASSWORD);
  await expect(page).toHaveURL("/inicio");
});

test("recuperación · /restablecer sin el enlace lleva a pedir uno nuevo", async ({ page }) => {
  await page.goto("/restablecer");
  await expect(page).toHaveURL("/recuperar?aviso=enlace");
  await expect(page.getByRole("alert").filter({ hasText: "El enlace no es válido o ha caducado" })).toBeVisible();
});

test("recuperación · un enlace inventado no sirve y avisa sin detalles", async ({ page }) => {
  await page.goto("/auth/confirm?token_hash=pkce_inventado&type=recovery&next=/restablecer");
  await expect(page).toHaveURL("/login?aviso=enlace");
  await expect(page.getByRole("alert").filter({ hasText: "El enlace no es válido o ha caducado" })).toBeVisible();
});

test("recuperación · un tipo de enlace que no usamos se rechaza", async ({ page }) => {
  await page.goto("/auth/confirm?token_hash=pkce_inventado&type=magiclink&next=/admin");
  await expect(page).toHaveURL("/login?aviso=enlace");
});

// --- AC-04 · sin sesión ----------------------------------------------------------------------------------------------------------

test("sin sesión · /inicio pide iniciar sesión y vuelve a /inicio tras entrar", async ({ page }) => {
  await page.goto("/inicio");
  await expect(page).toHaveURL("/login?next=/inicio");

  await fillLogin(page, PEOPLE.alicia.email, SEED_PASSWORD);
  await expect(page).toHaveURL("/inicio");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Hola, Alicia");
});

for (const hostile of ["//evil.example", "https://evil.example/inicio", "/\\evil.example", "javascript:alert(1)"]) {
  test(`sin sesión · un next hostil (${hostile}) se ignora y no saca del sitio`, async ({ page }) => {
    await page.goto(`/login?next=${encodeURIComponent(hostile)}`);
    await fillLogin(page, PEOPLE.gina.email, SEED_PASSWORD);

    await expect(page).toHaveURL(PEOPLE.gina.home); // su portada, no lo que pedía el enlace
    expect(new URL(page.url()).origin).toBe(WEB_URL);
  });
}

test("sin sesión · aunque se manipule el campo oculto next, la propia acción no redirige fuera", async ({ page }) => {
  // La página ya sanea `next` al pintar el formulario; aquí se salta esa capa y se comprueba la segunda, la de la Server Action.
  await page.goto("/login?next=/inicio");
  // Se cambia el valor justo al enviar (listener de captura en `document`, que corre antes que el de React): hacerlo al cargar es una carrera
  // con la hidratación, que en WebKit llega después y repone el valor.
  await page.evaluate((value) => {
    document.addEventListener(
      "submit",
      () => ((document.querySelector('input[name="next"]') as HTMLInputElement).value = value),
      true,
    );
  }, "//evil.example");
  await fillLogin(page, PEOPLE.gina.email, SEED_PASSWORD);

  await expect(page).toHaveURL(PEOPLE.gina.home);
  expect(new URL(page.url()).origin).toBe(WEB_URL);
});

test("sin sesión · GET /api/me sin cabecera Authorization es 401 problem+json", async ({ request }) => {
  const response = await request.get(`${API_URL}/api/me`);
  expect(response.status()).toBe(401);
  expect(response.headers()["content-type"]).toContain("application/problem+json");
  expect(await response.json()).toMatchObject({ status: 401, code: "unauthenticated" });
});

// --- Inicio y cierre de sesión ---------------------------------------------------------------------------------------------------

test("inicio de sesión · contraseña errónea y cuenta inexistente dan el mismo mensaje", async ({ page, browserName }) => {
  await login(page, PEOPLE.alicia.email, `${SEED_PASSWORD}-mal`);
  await expect(formAlert(page)).toHaveText(WRONG_CREDENTIALS);
  await expect(page).toHaveURL("/login");

  await fillLogin(page, uniqueEmail(`${browserName}-fantasma`), SEED_PASSWORD);
  await expect(formAlert(page)).toHaveText(WRONG_CREDENTIALS);
  await expect(page.getByLabel("Contraseña", { exact: true })).toHaveValue(""); // la contraseña no vuelve al navegador
});

test("inicio de sesión · el formulario vacío se señala campo a campo", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Entrar" }).click();
  const summary = formAlert(page);
  await expect(summary).toBeFocused();
  await expect(summary).toContainText("Escribe tu correo.");
  await expect(summary).toContainText("Escribe tu contraseña.");
});

test("inicio de sesión · con sesión, /login y /registro llevan a la portada", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  for (const path of ["/login", "/registro", "/recuperar"]) {
    await page.goto(path);
    await expect(page).toHaveURL("/inicio");
  }
});

test("inicio de sesión · cerrar sesión vuelve a /login y /inicio vuelve a pedirla", async ({ page, context }) => {
  await login(page, PEOPLE.alicia.email, SEED_PASSWORD);
  await expect(page).toHaveURL("/inicio");

  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL("/login");
  expect((await context.cookies()).filter((cookie) => cookie.name.includes("auth-token"))).toEqual([]);

  await page.goto("/inicio");
  await expect(page).toHaveURL("/login?next=/inicio");
});
