// SPEC-W-004 hito 6 · El asistente (`/asistente`) de extremo a extremo, contra `next start`, la API y el agente de E2E
// (`backend/tests/agents/e2e_server.py`), en los seis proyectos. Cada prueba decide qué dice el agente con marcadores en su pregunta
// (`[fixture:<nombre>]`, `[then:<nombre>]`, `[pace=<ms>]`: ver `helpers/chat.ts`).
//
// AC-01 a AC-07, AC-14, AC-20 y AC-22. AC-12 (roles) está en `roles.spec.ts` y el aspecto a 390 y 1.440 px en `responsive.spec.ts`.
//
// Presupuesto de envíos: la cuenta es la del worker y el tope es de 20 por hora y persona. Esta suite gasta 15 por cuenta en el peor caso
// (si un solo worker las corre todas); no añadas pruebas que envíen sin sumar aquí. `T1` 2, `T2` 1, `T3` 2, `T4` 1, `T5` 2, `T6` 2, `T7` 1,
// `T9` 1, `T10` 1, `T11a` 2.
import type { Page } from "@playwright/test";

import {
  CITATION_FIRST,
  CITATION_SECOND,
  CITATION_TITLE,
  CITATION_URL,
  EMPTY_THREAD,
  GENERIC_ERROR,
  INTERRUPTED_NOTE,
  LENGTH_FIRST,
  MISSING,
  NOTICE,
  UNAVAILABLE,
  alerts,
  conversationId,
  conversationLink,
  field,
  finished,
  mine,
  newTag,
  notices,
  openAssistant,
  openConversation,
  openList,
  question,
  reload,
  replies,
  send,
  sendButton,
  stopButton,
  thread,
} from "./helpers/chat";
import { AGENTS_KEY, WEB_URL } from "./helpers/env";
import { expect, test } from "./helpers/fixtures";
import { shown } from "./helpers/gastos";
import { expectEveryFieldLabelled, expectNoHorizontalScroll } from "./helpers/layout";

const useful = (reply: ReturnType<typeof replies>) => reply.getByRole("button", { name: "Útil", exact: true });

/** La primera respuesta de una conversación nueva: deja la conversación creada (`?c=`) para probar lo que ocurre en la segunda sin recargar la pantalla. */
async function startConversation(page: Page, tag: string): Promise<string> {
  await openAssistant(page);
  await send(page, question(tag, { fixture: "answer_with_citation" }));
  await finished(page);
  return conversationId(page);
}

test("asistente · la respuesta llega token a token con su fuente, se valora, sigue la conversación y sobrevive a recargar", async ({ gastosPage: page }) => {
  const tag = newTag();
  await openAssistant(page);
  await expect(shown(page.getByText(EMPTY_THREAD, { exact: true }))).toBeVisible();
  await expect(sendButton(page)).toBeDisabled(); // sin texto no se puede enviar

  // Cargando: la API espera al primer frame del agente, y el agente espera 800 ms antes de cada uno.
  await send(page, question(tag, { fixture: "answer_with_citation", pace: 800 }));
  await expect(stopButton(page)).toBeVisible();
  await expect(field(page)).toBeDisabled(); // no se escribe otra pregunta mientras llega la respuesta
  await expect(field(page)).toHaveValue(""); // y la enviada ya no está en el campo
  await expect(thread(page)).toHaveAttribute("aria-busy", "true");
  await expect(page.getByRole("status").filter({ hasText: "El asistente está escribiendo…" })).toBeAttached();
  await expect(page.getByText("Preparando la respuesta…", { exact: true })).toBeVisible();

  // La prueba de que el texto llega a medida que se escribe, a través de `next start`: el primer trozo se ve con la respuesta aún en curso y el
  // segundo, que el agente aún no ha escrito, no. Si algo acumulase el flujo, los dos llegarían a la vez al final.
  const reply = replies(page).last();
  await expect(reply).toContainText(CITATION_FIRST);
  await expect(reply).not.toContainText(CITATION_SECOND);
  await expect(stopButton(page)).toBeVisible();
  await expect(reply.getByRole("heading", { name: "Fuentes", exact: true })).toHaveCount(0);

  await finished(page);
  await expect(reply).toContainText(CITATION_SECOND);
  await expect(reply.getByRole("heading", { name: "Fuentes", exact: true })).toBeVisible();
  const source = reply.getByRole("link", { name: CITATION_TITLE, exact: true });
  await expect(source).toHaveAttribute("href", CITATION_URL);
  await expect(source).toHaveAttribute("target", "_blank");
  await expect(source).toHaveAttribute("rel", "noopener noreferrer");
  await expect(notices(page)).toHaveCount(1); // el aviso permanente, bajo el campo
  await conversationId(page);
  await expect(field(page)).toBeFocused(); // la pantalla se vuelve a montar con `?c=`: el foco pasa a la nueva

  await useful(reply).click();
  await expect(reply.getByRole("status").filter({ hasText: "Valoración guardada." })).toBeVisible();
  await expect(useful(reply)).toHaveAttribute("aria-pressed", "true");

  // Se puede cambiar de opinión: «No útil» pide un motivo de una lista cerrada y no deja guardar sin elegirlo.
  const notUseful = (message: ReturnType<typeof replies>) => message.getByRole("button", { name: "No útil", exact: true });
  await notUseful(reply).click();
  await expect(reply.getByRole("group", { name: "¿Qué ha fallado?" })).toBeVisible();
  await expect(reply.getByRole("button", { name: "Guardar valoración", exact: true })).toBeDisabled();
  await reply.getByLabel("No cita una fuente", { exact: true }).check();
  await reply.getByRole("button", { name: "Guardar valoración", exact: true }).click();
  await expect(reply.getByRole("status").filter({ hasText: "Valoración guardada." })).toBeVisible();
  await expect(notUseful(reply)).toHaveAttribute("aria-pressed", "true");
  await expect(useful(reply)).toHaveAttribute("aria-pressed", "false");

  // La segunda pregunta es de la misma conversación y no recarga la pantalla: el texto de «lista» queda en la región `role="status"`.
  await send(page, question(tag, { fixture: "abstention_no_source" }));
  await expect(page.getByRole("status").filter({ hasText: "Respuesta lista." })).toBeAttached();
  await expect(replies(page)).toHaveCount(2);
  await expect(mine(page)).toHaveCount(2);
  await expect(replies(page).last()).toContainText("No he encontrado una fuente oficial");
  await expect(field(page)).toBeFocused();

  await reload(page);
  await expect(replies(page)).toHaveCount(2);
  await expect(notUseful(replies(page).first())).toHaveAttribute("aria-pressed", "true"); // la valoración y su motivo sobreviven
  await expect(useful(replies(page).first())).toHaveAttribute("aria-pressed", "false");
  await notUseful(replies(page).first()).click();
  await expect(replies(page).first().getByLabel("No cita una fuente", { exact: true })).toBeChecked();
  await openList(page);
  await expect(conversationLink(page, tag)).toBeVisible();
  await expect(conversationLink(page, tag)).toHaveAttribute("aria-current", "true");
});

test("asistente · una abstención deriva a un asesor y repite el aviso dentro del mensaje (Ctrl+Intro envía)", async ({ gastosPage: page }) => {
  const tag = newTag();
  await openAssistant(page);
  await field(page).fill(question(tag, { fixture: "abstention_professional" }));
  await field(page).press("Control+Enter");
  await finished(page);

  const reply = replies(page).last();
  await expect(reply).toContainText("Esa decisión depende de tu situación personal");
  await expect(reply.getByText("Para tu caso, consúltalo con un asesor.", { exact: true })).toBeVisible(); // la cuenta no tiene gestor
  await expect(reply.getByText(NOTICE, { exact: true })).toHaveCount(1);
  await expect(notices(page)).toHaveCount(2); // el de dentro del mensaje y el de bajo el campo
  await expect(reply.getByRole("heading", { name: "Fuentes", exact: true })).toHaveCount(0);
  await expect(reply.getByRole("alert")).toHaveCount(0);
  await expect(useful(reply)).toBeVisible();
});

test("asistente · «Detener» corta la respuesta: queda lo recibido como interrumpido y no se valora hasta recargar", async ({ gastosPage: page }) => {
  const tag = newTag();
  await startConversation(page, tag);

  await send(page, `Otra ${tag} [fixture:answer_length][pace=1500]`);
  const reply = replies(page).last();
  await expect(reply).toContainText(LENGTH_FIRST);
  await stopButton(page).click();
  await finished(page);

  await expect(reply).toContainText(LENGTH_FIRST);
  await expect(reply).not.toContainText("ventas al por menor"); // el segundo trozo, que no llegó a escribirse
  await expect(alerts(reply, INTERRUPTED_NOTE)).toBeVisible();
  await expect(useful(reply)).toHaveCount(0);
  await expect(field(page)).toBeFocused();

  // La API guarda lo recibido cuando nota el corte, un instante después: se recarga hasta verlo guardado y entonces sí se puede valorar.
  await expect(async () => {
    await reload(page);
    await expect(alerts(replies(page).last(), INTERRUPTED_NOTE)).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 20_000 });
  await expect(replies(page).last()).toContainText(LENGTH_FIRST);
  await expect(replies(page).last()).not.toContainText("ventas al por menor");
  await expect(useful(replies(page).last())).toBeVisible();
});

test("asistente · salir de la pantalla con la respuesta a medias la deja interrumpida", async ({ gastosPage: page }) => {
  const tag = newTag();
  await openAssistant(page);
  await send(page, question(tag, { fixture: "answer_length", pace: 1000 }));
  await expect(replies(page).last()).toContainText(LENGTH_FIRST);

  await page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Inicio", exact: true }).click();
  await expect(page).toHaveURL(/\/inicio$/);

  await expect(async () => {
    await openAssistant(page);
    await openConversation(page, tag);
    await expect(alerts(replies(page).last(), INTERRUPTED_NOTE)).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 20_000 });
  await expect(replies(page).last()).toContainText(LENGTH_FIRST);
  await expect(replies(page).last()).not.toContainText("ventas al por menor");
});

test("asistente · un error dentro del flujo enseña un texto fijo, nunca el del agente, y la respuesta se puede valorar", async ({ gastosPage: page }) => {
  const tag = newTag();
  await startConversation(page, tag);

  await send(page, `Otra ${tag} [fixture:error_tool]`);
  await finished(page);
  const reply = replies(page).last();
  await expect(alerts(reply, "No se han podido consultar tus datos ahora mismo. Inténtalo de nuevo.")).toBeVisible();
  await expect(reply).not.toContainText("No se pudieron consultar"); // el texto del agente (ver contracts/examples/chat/error_tool.sse)
  await expect(useful(reply)).toBeVisible(); // el servidor la guardó como `error`
  await expect(field(page)).toBeFocused();

  await reload(page); // lo guardado no lleva el código: texto genérico
  await expect(alerts(replies(page).last(), GENERIC_ERROR)).toBeVisible();
});

test("asistente · si el agente falla antes del primer frame se ofrece «Reintentar» y el reintento responde", async ({ gastosPage: page, expectedBrowserErrors }) => {
  expectedBrowserErrors.push(/^console\.error: Failed to load resource: the server responded with a status of 503 \(Service Unavailable\) \(en \/asistente\/enviar\)$/);
  const tag = newTag();
  await openAssistant(page);
  await send(page, question(tag, { fixture: "http_unavailable", then: "answer_with_citation" }));

  const failure = page.getByRole("alert").filter({ hasText: UNAVAILABLE });
  await expect(failure).toBeVisible();
  await expect(mine(page)).toHaveCount(1); // la pregunta sigue a la vista
  await expect(replies(page)).toHaveCount(0);
  await expect(field(page)).toBeFocused();

  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await finished(page);
  await conversationId(page);
  await expect(failure).toHaveCount(0);
  await expect(replies(page).last()).toContainText(CITATION_FIRST);
  // El reintento es una pregunta más (SPEC-W-004 §5.4): en el historial la primera queda sin respuesta y la segunda con ella.
  await expect(mine(page).first()).toBeVisible();
  await expect(replies(page)).toHaveCount(1);
});

test("asistente · el texto del agente se pinta como texto: ni HTML, ni Markdown, ni enlaces que no sean https", async ({ gastosPage: page }) => {
  const dialogs: string[] = [];
  page.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    void dialog.dismiss();
  });
  const tag = newTag();
  await openAssistant(page);
  await send(page, question(tag, { fixture: "hostile" }));
  await finished(page);
  await conversationId(page);

  const reply = replies(page).last();
  await expect(reply).toContainText("<img src=x onerror=");
  await expect(reply).toContainText("**negrita**");
  await expect(reply).toContainText("[enlace](javascript:alert(1))");
  await expect(reply).toContainText("<script>alert(1)</script>");
  await expect(reply.getByText("<b>Título en HTML</b>", { exact: true })).toBeVisible();
  await expect(reply.locator("img, script, b, i, strong, em, code")).toHaveCount(0);
  await expect(reply.getByRole("link")).toHaveCount(0); // la cita es `http:`: se enseña, pero no es un enlace
  await expect(page).toHaveTitle(/Asistente/); // el `onerror` no se ejecutó
  expect(dialogs).toEqual([]);
  await expectNoHorizontalScroll(page); // la palabra de 300 caracteres sin espacios no desborda
});

test("asistente · el contador, el límite de 2.000 caracteres y Intro como salto de línea", async ({ gastosPage: page }) => {
  await openAssistant(page);
  await field(page).fill("a".repeat(2000));
  await expect(shown(page.getByText(/^2000 de 2000 caracteres/))).toBeVisible();
  await expect(sendButton(page)).toBeEnabled();

  await field(page).fill("a".repeat(2001));
  await expect(shown(page.getByText(/^Te pasas 1 caracteres \(máximo 2000\)/))).toBeVisible();
  await expect(sendButton(page)).toBeDisabled();
  await expect(field(page)).toHaveAttribute("aria-invalid", "true");

  await field(page).fill("   "); // solo espacios: no cuenta
  await expect(sendButton(page)).toBeDisabled();

  await field(page).fill("uno");
  await field(page).press("Enter"); // Intro solo escribe un salto de línea
  await expect(field(page)).toHaveValue("uno\n");
  await expect(mine(page)).toHaveCount(0);
});

test("asistente · borrar una conversación pide confirmación, la quita de la lista y su dirección deja de existir", async ({ gastosPage: page }) => {
  const tag = newTag();
  const id = await startConversation(page, tag);

  await page.getByRole("button", { name: "Borrar conversación", exact: true }).click();
  const confirmation = page.getByRole("group").filter({ hasText: "¿Borrar esta conversación?" });
  await expect(confirmation).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancelar", exact: true })).toBeFocused(); // por defecto, la opción segura
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(confirmation).toHaveCount(0);
  await expect(page).toHaveURL(/\/asistente\?c=[0-9a-f-]{36}$/);
  await expect(replies(page)).toHaveCount(1);

  await page.getByRole("button", { name: "Borrar conversación", exact: true }).click();
  await page.getByRole("button", { name: "Sí, borrar", exact: true }).click();
  await expect(page).toHaveURL(/\/asistente$/);
  await expect(shown(page.getByText(EMPTY_THREAD, { exact: true }))).toBeVisible();
  await openList(page);
  await expect(conversationLink(page, tag)).toHaveCount(0);

  await page.goto(`/asistente?c=${id}`);
  await expect(shown(page.getByText(MISSING, { exact: true }))).toBeVisible();
});

test("asistente · la conversación de una cuenta no se ve ni se abre desde otra", async ({ gastosPage: page, pageAs }) => {
  const tag = newTag();
  const id = await startConversation(page, tag);

  const other = await pageAs("alicia");
  await other.goto(`/asistente?c=${id}`);
  await expect(other.getByRole("heading", { level: 1, name: "Asistente", exact: true })).toBeVisible();
  await expect(shown(other.getByText(MISSING, { exact: true }))).toBeVisible();
  await expect(mine(other)).toHaveCount(0);
  await openList(other);
  await expect(conversationLink(other, tag)).toHaveCount(0);
});

// --- La frontera (AC-20) ---------------------------------------------------------------------------------------------------------------

/** La sesión de Supabase vive en una cookie (a veces en trozos `.0`, `.1`) con `access_token` y `refresh_token`. */
function sessionSecrets(cookies: { name: string; value: string }[]): string[] {
  const joined = cookies
    .filter((cookie) => /-auth-token(\.\d+)?$/.test(cookie.name)) // no `-auth-token-code-verifier`
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((cookie) => cookie.value)
    .join("");
  const decoded = joined.startsWith("base64-") ? Buffer.from(joined.slice("base64-".length), "base64url").toString("utf8") : decodeURIComponent(joined);
  const session = JSON.parse(decoded) as { access_token?: string; refresh_token?: string };
  return [session.access_token, session.refresh_token].filter((value): value is string => typeof value === "string" && value.length >= 10);
}

test("asistente · lo que llega al navegador (HTML, scripts, flujo y peticiones) no lleva la sesión ni la clave de agentes", async ({ gastosPage: page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-1440", "Es igual en los seis proyectos: se mira una vez, como bundle.spec.ts.");
  const bodies: { url: string; text: string }[] = [];
  const sent: { url: string; authorization: string | undefined }[] = [];
  page.on("request", (request) => sent.push({ url: request.url(), authorization: request.headers()["authorization"] }));
  page.on("response", async (response) => {
    if (!["document", "script", "fetch", "xhr"].includes(response.request().resourceType())) return;
    try {
      bodies.push({ url: response.url(), text: await response.text() });
    } catch {
      // redirecciones y respuestas sin cuerpo
    }
  });

  await openAssistant(page);
  await send(page, question(newTag(), { fixture: "answer_with_citation" }));
  await finished(page);
  await page.waitForLoadState("networkidle");

  // Chromium no deja leer por `response.text()` un `text/event-stream`: el flujo se lee con un `fetch` dentro de la página, que es lo que ve ella.
  const stream = await page.evaluate(async (content) => {
    const response = await fetch("/asistente/enviar", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ conversation_id: null, content }) });
    return {
      status: response.status,
      type: response.headers.get("content-type") ?? "",
      cacheControl: response.headers.get("cache-control") ?? "",
      buffering: response.headers.get("x-accel-buffering") ?? "",
      headers: [...response.headers.keys()],
      text: await response.text(),
    };
  }, question(newTag(), { fixture: "answer_with_citation" }));
  expect(stream.status).toBe(200);
  expect(stream.type).toContain("text/event-stream");
  // Cabeceras que impiden que un intermediario (compresión, proxy, CDN) acumule el flujo: en local nada lo acumularía, pero en el despliegue sí podría.
  expect(stream.cacheControl.split(",").map((part) => part.trim())).toEqual(expect.arrayContaining(["private", "no-store", "no-transform"]));
  expect(stream.buffering).toBe("no");
  expect(stream.text, "la prueba debe ver el flujo").toContain("event: done");
  expect(stream.headers).not.toContain("set-cookie");
  bodies.push({ url: `${WEB_URL}/asistente/enviar`, text: stream.text + JSON.stringify(stream.headers) });

  const secrets = sessionSecrets(await page.context().cookies());
  expect(secrets.length, "la prueba debe tener la sesión que buscar").toBe(2);
  expect(bodies.some((body) => body.url.includes("/_next/static/")), "la prueba debe ver los scripts del cliente").toBe(true);
  const leaks = bodies.flatMap(({ url, text }) => [...secrets, AGENTS_KEY].filter((secret) => text.includes(secret)).map(() => `${new URL(url).pathname} contiene un secreto`));
  expect(leaks).toEqual([]);
  // El navegador no manda el JWT a ningún sitio: la sesión va en cookies y el Route Handler pone el `Authorization` hacia la API.
  expect(sent.filter((request) => request.authorization !== undefined).map((request) => new URL(request.url).pathname)).toEqual([]);
});

test("asistente · el envío rechaza otro origen y a quien no tiene sesión", async ({ gastosPage: page, playwright }) => {
  const url = `${WEB_URL}/asistente/enviar`;
  const data = { conversation_id: null, content: `x ${newTag()} [fixture:answer_with_citation]` };

  const foreign = await page.request.post(url, { headers: { origin: "https://sitio-ajeno.example.test" }, data, maxRedirects: 0 });
  expect(foreign.status()).toBe(403);
  expect(((await foreign.json()) as { code: string }).code).toBe("forbidden");
  const crossSite = await page.request.post(url, { headers: { origin: WEB_URL, "sec-fetch-site": "cross-site" }, data, maxRedirects: 0 });
  expect(crossSite.status()).toBe(403);

  const anonymous = await playwright.request.newContext();
  try {
    const response = await anonymous.post(url, { headers: { origin: WEB_URL }, data, maxRedirects: 0 });
    expect(response.headers()["content-type"] ?? "").not.toContain("text/event-stream");
    expect(await response.text()).not.toContain("event:");
    expect([307, 308, 401]).toContain(response.status());
  } finally {
    await anonymous.dispose();
  }
});

test("asistente · sin sesión, /asistente lleva a /login", async ({ page }) => {
  await page.goto("/asistente");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByLabel("Tu pregunta", { exact: true })).toHaveCount(0);
});

// --- La pantalla (AC-22) ---------------------------------------------------------------------------------------------------------------

test("asistente · pantalla vacía: campo con etiqueta y contador, foco visible, aviso permanente y sin scroll horizontal", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await openAssistant(page);
  await expectNoHorizontalScroll(page);
  await expectEveryFieldLabelled(page);
  await expect(shown(page.getByText(/^0 de 2000 caracteres/))).toBeVisible();
  await expect(notices(page)).toHaveCount(1);
  await expect(sendButton(page)).toBeDisabled();

  await field(page).focus();
  await expect(field(page)).toBeFocused();
  const ring = await field(page).evaluate((element) => getComputedStyle(element).boxShadow);
  expect(ring, "el campo enfocado debe verse (anillo de foco)").not.toBe("none");
});
