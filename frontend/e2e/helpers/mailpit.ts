// Buzón de pruebas de Supabase local (Mailpit): lo que «enviaría» Supabase Auth se lee aquí. Sin dependencias.
import { MAILPIT_URL, WEB_URL } from "./env";

type Summary = { ID: string; Subject: string };
type Message = { Subject: string; HTML: string };

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${MAILPIT_URL}${path}`, { signal: AbortSignal.timeout(10_000) });
  if (!response.ok) throw new Error(`Mailpit respondió ${response.status} a ${path}`);
  return (await response.json()) as T;
}

/** Correos para ese destinatario, del más reciente al más antiguo. */
async function messagesTo(recipient: string): Promise<Summary[]> {
  const query = encodeURIComponent(`to:${recipient}`);
  return (await getJson<{ messages: Summary[] }>(`/api/v1/search?query=${query}&limit=20`)).messages;
}

export async function countMessagesTo(recipient: string): Promise<number> {
  return (await messagesTo(recipient)).length;
}

/** Enlace a /auth/confirm del cuerpo HTML del correo (los `&` vienen como `&amp;`), reubicado en la URL de la aplicación. */
function confirmLink(html: string): URL | null {
  const match = /href="([^"]*\/auth\/confirm\?[^"]+)"/.exec(html);
  if (!match?.[1]) return null;
  const link = new URL(match[1].replaceAll("&amp;", "&"));
  return new URL(`${link.pathname}${link.search}`, WEB_URL);
}

/**
 * Espera el correo de Supabase Auth con el enlace de `type` (`email` = confirmar cuenta, `recovery` = restablecer contraseña) para
 * `recipient` y devuelve ese enlace. Los correos llegan de forma asíncrona: se sondea cada 250 ms hasta `timeoutMs`.
 */
export async function waitForLink(recipient: string, type: "email" | "recovery", timeoutMs = 15_000): Promise<URL> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    for (const summary of await messagesTo(recipient)) {
      const link = confirmLink((await getJson<Message>(`/api/v1/message/${summary.ID}`)).HTML);
      if (link?.searchParams.get("type") === type) return link;
    }
    if (Date.now() > deadline) throw new Error(`No llegó a Mailpit un correo «${type}» para ${recipient} en ${timeoutMs} ms`);
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}
