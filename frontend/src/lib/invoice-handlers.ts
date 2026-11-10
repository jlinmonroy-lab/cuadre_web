// Lo que deciden los Route Handlers de facturas (vista previa y descarga del PDF), sin red ni Next: puro, lo ejecutan directamente los tests.
//
// El navegador no tiene el JWT ni ve nunca la URL de Storage: la descarga pasa por el servidor de Next, que pide el PDF a la API y lo reenvía. Aquí
// se decide QUÉ cabeceras de la API se reenvían (tipo, nombre y no-store; nada más) y qué texto se enseña cuando algo falla.
import type { InvoicePreview } from "./invoices.ts";
import { fieldErrorsFromInvoiceProblem, type InvoiceErrors, type PreviewBase } from "./invoices-form.ts";
import type { Problem } from "./problems.ts";

// --- Vista previa -----------------------------------------------------------------------------------------------------------------------

/** Lo que el navegador recibe de `POST /facturas/vista-previa`. */
export type PreviewError = { status: "error"; code: string; message: string; fieldErrors: InvoiceErrors; missing?: { field: string; label: string }[] };
export type PreviewReply = { status: "ok"; preview: InvoicePreview; base: PreviewBase } | PreviewError;

/** Los campos cuyo error se enseña mientras se teclea; la fecha y el concepto se avisan al emitir (aquí van rellenos con valores neutros). */
const PREVIEW_FIELDS = new Set(["client_id", "series_id", "base", "vat_rate"]);
const REVIEW = "Revisa los datos de la factura para ver la vista previa.";

/** Un error de la API → lo que enseña la vista previa: errores junto a su campo (solo los del cliente, la serie, el importe y el IVA) o un titular. */
export function previewError(problem: Problem): PreviewError {
  if (problem.code === "profile_incomplete" && problem.missing) {
    return { status: "error", code: problem.code, message: problem.message, fieldErrors: {}, missing: problem.missing };
  }
  const all = fieldErrorsFromInvoiceProblem(problem, "invoice") ?? {};
  const fieldErrors = Object.fromEntries(Object.entries(all).filter(([name]) => PREVIEW_FIELDS.has(name)));
  // Un error de campos cuyo único error es de los que se avisan al emitir (fecha, concepto) no dice nada útil aquí: un titular neutro.
  const onlyLaterFields = Object.keys(fieldErrors).length === 0 && Object.keys(all).length > 0;
  return { status: "error", code: problem.code, message: onlyLaterFields ? REVIEW : problem.message, fieldErrors };
}

// --- Descarga del PDF -------------------------------------------------------------------------------------------------------------------

const SAFE_PDF_NAME = /^[A-Za-z0-9._-]{1,40}\.pdf$/;
const PDF_TYPE = /^application\/pdf(\s*;.*)?$/i;

/** El nombre del archivo de un `Content-Disposition: attachment; filename="2026-001.pdf"`; si no es un nombre sencillo, `factura.pdf`. */
export function safePdfFilename(disposition: string | null): string {
  const match = /filename="([^"]*)"/.exec(disposition ?? "");
  const name = match?.[1] ?? "";
  return SAFE_PDF_NAME.test(name) && !name.includes("..") ? name : "factura.pdf";
}

/**
 * Las cabeceras con las que se entrega el PDF: SIEMPRE `application/pdf`, `attachment` con un nombre sencillo y `private, no-store`. `null` si la
 * API no contestó con un PDF (entonces no se reenvía el cuerpo).
 */
export function pdfHeaders(get: (name: string) => string | null): Record<string, string> | null {
  if (!PDF_TYPE.test(get("content-type") ?? "")) return null;
  return {
    "content-type": "application/pdf",
    "content-disposition": `attachment; filename="${safePdfFilename(get("content-disposition"))}"`,
    "cache-control": "private, no-store",
    "x-content-type-options": "nosniff",
  };
}

export type PdfFailure = { status: number; text: string; retryAfter?: number };

const PDF_TEXT: Record<number, string> = {
  401: "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.",
  403: "No tienes acceso a esta factura.",
  404: "No encontramos esa factura.",
};
const PDF_UNAVAILABLE = "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.";

/** Qué se contesta cuando la API no entrega el PDF. El texto de un 409 (`invoice_pdf_pending` / `invoice_pdf_corrupt`) es el del servidor. */
export function pdfFailure(problem: Problem): PdfFailure {
  const known = PDF_TEXT[problem.status];
  if (known) return { status: problem.status, text: known };
  if (problem.status === 409) return { status: 409, text: problem.message };
  return { status: 503, text: PDF_UNAVAILABLE, ...(problem.retryAfter ? { retryAfter: problem.retryAfter } : {}) };
}
