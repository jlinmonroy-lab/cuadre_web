// Lógica de los Route Handlers de facturas: `POST /facturas/vista-previa` (la vista previa en directo) y `GET /facturas/<id>/pdf` (la descarga).
//
// La vista previa va por un Route Handler y no por una Server Action porque Next despacha las acciones de una en una por cliente: aquí cada
// cambio del formulario cancela la petición anterior y solo vale la última. La descarga va por el servidor de Next para que el navegador no tenga
// el JWT ni vea nunca la URL de Storage. A diferencia de las Server Actions, Next no comprueba el origen de un Route Handler: la vista previa
// (que usa la sesión para pedir datos de la persona) lo comprueba aquí (defensa CSRF).
import "server-only";

import { apiFor, sessionToken } from "@/lib/api-server";
import { pdfFailure, pdfHeaders, previewError, type PdfFailure, type PreviewReply } from "@/lib/invoice-handlers";
import { madridToday } from "@/lib/invoices";
import { isInvoiceId, toPreviewRequest, valuesFromInvoiceForm } from "@/lib/invoices-form";
import { SERVICE_UNAVAILABLE, describeProblem } from "@/lib/problems";
import { isSameOrigin, originHeaders } from "@/lib/same-origin";

const NO_STORE = { "cache-control": "no-store" };
const MAX_PREVIEW_BODY = 4_096;
const SESSION_EXPIRED = "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.";

function reply(body: PreviewReply, status = 200, retryAfter?: number): Response {
  return Response.json(body, { status, headers: { ...NO_STORE, ...(retryAfter ? { "retry-after": String(retryAfter) } : {}) } });
}

const failure = (status: number, code: string, message: string): Response =>
  reply({ status: "error", code, message, fieldErrors: {} }, status);

/** `POST /facturas/vista-previa`: pide a la API lo que se emitiría (ámbito, importes y mención) con lo que lleva escrito el formulario. */
export async function handlePreview(request: Request): Promise<Response> {
  if (!isSameOrigin(originHeaders(request.headers))) return failure(403, "forbidden", "Esta petición no se admite desde otro sitio.");

  const text = await request.text();
  if (text.length > MAX_PREVIEW_BODY) return failure(413, "payload_too_large", "La petición es demasiado grande.");
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    return failure(400, "bad_request", "La petición no es válida.");
  }
  const fields = typeof json === "object" && json !== null && !Array.isArray(json) ? (json as Record<string, unknown>) : {};

  const token = await sessionToken();
  if (!token) return failure(401, "session", SESSION_EXPIRED);

  const { body, base } = toPreviewRequest(valuesFromInvoiceForm((name) => fields[name]), madridToday(new Date()));
  try {
    const result = await apiFor(token).POST("/api/invoices/preview", { body });
    if (result.data) return reply({ status: "ok", preview: result.data, base });
    const problem = describeProblem({ status: result.response.status, body: result.error, retryAfter: result.response.headers.get("retry-after") });
    // La API rechazó el token: para el navegador es «sesión caducada» (no se puede reintentar sin volver a entrar).
    if (result.response.status === 401) return failure(401, "session", SESSION_EXPIRED);
    return reply(previewError(problem), problem.status, problem.retryAfter);
  } catch {
    return reply(previewError(SERVICE_UNAVAILABLE), 503);
  }
}

function plain({ status, text, retryAfter }: PdfFailure): Response {
  return new Response(text, {
    status,
    headers: { ...NO_STORE, "content-type": "text/plain; charset=utf-8", ...(retryAfter ? { "retry-after": String(retryAfter) } : {}) },
  });
}

/**
 * `GET /facturas/<id>/pdf`: el PDF de una factura, con la huella ya comprobada por la API. Se reenvía como adjunto con `Cache-Control: private,
 * no-store`; si la API no entrega un PDF (pendiente, alterado, sin Storage…) se contesta con el texto del error en español.
 */
export async function handleInvoicePdf(invoiceId: string): Promise<Response> {
  if (!isInvoiceId(invoiceId)) return plain(pdfFailure(describeProblem({ status: 404, body: null })));
  const token = await sessionToken();
  if (!token) return plain(pdfFailure(describeProblem({ status: 401, body: null })));

  let result;
  try {
    result = await apiFor(token).GET("/api/invoices/{invoice_id}/pdf", { params: { path: { invoice_id: invoiceId } }, parseAs: "arrayBuffer" });
  } catch {
    return plain(pdfFailure(SERVICE_UNAVAILABLE));
  }
  if (result.response.ok && result.data) {
    const headers = pdfHeaders((name) => result.response.headers.get(name));
    if (headers) return new Response(result.data as ArrayBuffer, { status: 200, headers });
    return plain(pdfFailure(SERVICE_UNAVAILABLE)); // la API contestó 200 con algo que no es un PDF: no se reenvía
  }
  return plain(
    pdfFailure(describeProblem({ status: result.response.status, body: result.error, retryAfter: result.response.headers.get("retry-after") })),
  );
}
