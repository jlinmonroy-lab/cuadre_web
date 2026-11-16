// POST /asistente/enviar: reenvía el mensaje a la API del chat y devuelve su flujo SSE sin acumularlo (SPEC-W-004 D-02).
// El navegador no tiene el JWT; la sesión se lee de las cookies. Sin `dynamic` ni `runtime`: con `cacheComponents` no se admiten.
import { sessionToken } from "@/lib/api-server";
import { handleSend } from "@/lib/chat-handler";
import { apiBaseUrl } from "@/lib/env";

export const maxDuration = 100; // el plazo total del agente es de 90 s (D-12) más el guardado

export async function POST(request: Request) {
  return handleSend(request, { token: sessionToken, backend: apiBaseUrl, fetch: (input, init) => fetch(input, init) });
}
