// Lógica de los Route Handlers de descarga del gestor: `GET /cartera/<owner>/facturas/<id>/pdf` y `GET /cartera/<owner>/documentos/<id>/original`.
//
// Piden a la API una URL firmada NUEVA (≈ 60 s) con la sesión del GESTOR y redirigen a ella: el navegador nunca ve el JWT ni la clave de Storage, y la
// URL no se guarda en ningún sitio. Cada pulsación es una lectura y queda registrada en el acceso del autónomo (una entrada por petición). El enlace
// de la página es un `<a>` normal: sin precarga, para que mirar la ficha no descargue nada.
import "server-only";

import { apiFor, sessionToken } from "@/lib/api-server";
import { httpUrl } from "@/lib/documents";
import { isUuid } from "@/lib/gestor";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";

const NO_STORE = { "cache-control": "no-store" };
const plain = (status: number, text: string): Response => new Response(text, { status, headers: { ...NO_STORE, "content-type": "text/plain; charset=utf-8" } });

type Kind = "pdf" | "original";
const PENDING: Record<Kind, string> = {
  pdf: "El PDF de esta factura todavía no está disponible.",
  original: "El archivo todavía no está disponible.",
};

/** `GET`: redirige (302) a una URL firmada de la factura o del documento. Cualquier id que no sea un UUID es «no encontrado» sin llamar a la API. */
export async function handleGestorDownload(kind: Kind, ownerId: string, resourceId: string): Promise<Response> {
  if (!isUuid(ownerId) || !isUuid(resourceId)) return plain(404, "No encontramos ese archivo.");
  const token = await sessionToken();
  if (!token) return plain(401, "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.");

  const api = apiFor(token);
  let result;
  try {
    result =
      kind === "pdf"
        ? await api.GET("/api/gestor/autonomos/{owner_id}/facturas/{invoice_id}/pdf", { params: { path: { owner_id: ownerId, invoice_id: resourceId } } })
        : await api.GET("/api/gestor/autonomos/{owner_id}/documentos/{document_id}/original", { params: { path: { owner_id: ownerId, document_id: resourceId } } });
  } catch {
    return plain(503, SERVICE_UNAVAILABLE.message);
  }
  const target = result.data ? httpUrl(result.data.url) : null;
  if (target) return new Response(null, { status: 302, headers: { ...NO_STORE, location: target, "referrer-policy": "no-referrer" } });

  switch (result.response.status) {
    case 401:
    case 403:
      return plain(result.response.status, "No tienes acceso a este archivo.");
    case 404:
      return plain(404, "No encontramos ese archivo.");
    case 409:
      return plain(409, PENDING[kind]);
    default:
      return plain(503, SERVICE_UNAVAILABLE.message);
  }
}
