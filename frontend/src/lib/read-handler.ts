// Lógica de los Route Handlers `POST /gastos/<id>/leer` y `/releer`: piden a la API que lea el documento (complete / retry) y esperan
// su respuesta, que puede tardar hasta 45 s. Van por Route Handlers y no por Server Actions porque Next despacha las acciones de una
// en una por cliente (varios archivos se leerían uno detrás de otro y el refresco automático se congelaría).
//
// El navegador no tiene el JWT: la sesión se lee de las cookies, igual que en el resto de la web. A diferencia de las Server Actions,
// Next no comprueba el origen de un Route Handler: se comprueba aquí (defensa CSRF).
import "server-only";

import { apiFor, sessionToken } from "@/lib/api-server";
import { httpUrl, isDocumentId } from "@/lib/documents";
import { SERVICE_UNAVAILABLE, describeProblem, type Problem } from "@/lib/problems";
import { isSameOrigin, originHeaders } from "@/lib/same-origin";

export type ReadOperation = "complete" | "retry";

const NO_STORE = { "cache-control": "no-store" };

function reply({ status, code, message, retryAfter }: Problem): Response {
  return Response.json({ code, message }, { status, headers: { ...NO_STORE, ...(retryAfter ? { "retry-after": String(retryAfter) } : {}) } });
}

/**
 * `GET /gastos/<id>/original`: redirige a una URL firmada NUEVA del archivo (60 s). El visor (`<img>`, `<iframe>`) y el enlace
 * «Abrir el original» apuntan aquí en vez de a la URL firmada, que caducaría mientras la persona revisa los datos.
 */
export async function handleOriginal(documentId: string): Promise<Response> {
  const plain = (status: number, text: string) => new Response(text, { status, headers: { ...NO_STORE, "content-type": "text/plain; charset=utf-8" } });
  if (!isDocumentId(documentId)) return plain(404, "No encontramos ese documento.");
  const token = await sessionToken();
  if (!token) return plain(401, "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.");

  let result;
  try {
    result = await apiFor(token).GET("/api/documents/{document_id}/preview", { params: { path: { document_id: documentId } } });
  } catch {
    return plain(503, SERVICE_UNAVAILABLE.message);
  }
  const target = result.data ? httpUrl(result.data.url) : null;
  if (target) return new Response(null, { status: 302, headers: { ...NO_STORE, location: target, "referrer-policy": "no-referrer" } });

  switch (result.response.status) {
    case 401:
    case 403:
      return plain(result.response.status, "No tienes acceso a este documento.");
    case 404:
      return plain(404, "No encontramos ese documento.");
    case 409:
      return plain(409, "El archivo todavía no está disponible.");
    default:
      return plain(503, SERVICE_UNAVAILABLE.message);
  }
}

export async function handleRead(request: Request, documentId: string, operation: ReadOperation): Promise<Response> {
  if (!isSameOrigin(originHeaders(request.headers))) {
    return reply({ status: 403, code: "forbidden", message: "Esta petición no se admite desde otro sitio." });
  }
  if (!isDocumentId(documentId)) return reply({ status: 404, code: "document_not_found", message: "No encontramos ese documento." });

  const token = await sessionToken();
  if (!token) return reply({ status: 401, code: "session", message: "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar." });
  const api = apiFor(token);
  const path = { params: { path: { document_id: documentId } } };

  try {
    const result =
      operation === "complete"
        ? await api.POST("/api/documents/{document_id}/complete", path)
        : await api.POST("/api/documents/{document_id}/retry", path);
    if (result.data) return Response.json({ id: result.data.id, status: result.data.status }, { headers: NO_STORE });

    const problem = describeProblem({
      status: result.response.status,
      body: result.error,
      retryAfter: result.response.headers.get("retry-after"),
    });
    // La API rechazó el token: para el navegador es «sesión caducada» (no se puede reintentar sin volver a entrar).
    return reply(result.response.status === 401 ? { ...problem, code: "session" } : problem);
  } catch {
    return reply(SERVICE_UNAVAILABLE);
  }
}
