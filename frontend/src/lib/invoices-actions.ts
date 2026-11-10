"use server";

// Server Actions de facturas: emitir, rectificar, cobrar y generar el PDF. Todo lo que reciben es entrada no confiable (las Server Actions son POST
// públicos y el proxy no las ve): se valida la forma aquí, se comprueba la sesión y la API vuelve a decidir (403 al gestor, 404 a la factura ajena,
// 409 y 422 con su texto). No hay ninguna regla fiscal aquí: el ámbito, el IVA, la retención y la mención los calcula el servidor. Ni el concepto,
// ni el motivo, ni los datos del cliente se escriben en ningún registro: los errores solo llevan el texto que devuelve el servidor.
//
// Emitir y rectificar NO esperan al PDF para dar la factura por emitida: la API contesta 201 con `pdf_status` `ready` o `pending`. Al terminar, la
// persona va a la factura nueva (`?emitida=1`), que es donde se descarga o se genera el PDF.
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import type { FormState } from "@/lib/form-state";
import { invoiceFailure, isInvoiceId, toInvoiceBody, toRectificationBody, valuesFromInvoiceForm, valuesFromRectifyForm, type InvoiceFormState } from "@/lib/invoices-form";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";

const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };
const UNKNOWN_INVOICE: FormState = { status: "error", message: "No encontramos esa factura." };

/** «Emitir factura»: todo o nada, con todos los errores a la vez. Con éxito lleva a la factura recién emitida. */
export async function issueInvoice(_previous: InvoiceFormState, formData: FormData): Promise<InvoiceFormState> {
  const values = valuesFromInvoiceForm((name) => formData.get(name));
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/invoices", { body: toInvoiceBody(values) });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) redirect(`/facturas/${result.data.id}?emitida=1`);
  return invoiceFailure(problemOf(result.response, result.error), values, "invoice");
}

/** «Emitir rectificativa» de la factura `invoiceId` (`useActionState` con el id enlazado). Con éxito lleva a la rectificativa. */
export async function issueRectification(invoiceId: string, _previous: InvoiceFormState, formData: FormData): Promise<InvoiceFormState> {
  if (!isInvoiceId(invoiceId)) return UNKNOWN_INVOICE;
  const values = valuesFromRectifyForm((name) => formData.get(name));
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/invoices/{invoice_id}/rectifications", {
      params: { path: { invoice_id: invoiceId } },
      body: toRectificationBody(values),
    });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) redirect(`/facturas/${result.data.id}?emitida=1`);
  const problem = problemOf(result.response, result.error);
  // Otra rectificación cambió la factura mientras se rellenaba el formulario: se refresca para que la pantalla enseñe la base vigente nueva.
  if (problem.code === "invoice_changed" || problem.status === 404) refresh();
  return invoiceFailure(problem, values, "rectification");
}

/** «Marcar como cobrada» / «Marcar como pendiente» (`paid` es lo que se quiere, no lo que hay). Solo `paid_at` de una factura cambia. */
export async function setInvoicePaid(invoiceId: string, paid: boolean): Promise<FormState> {
  if (!isInvoiceId(invoiceId)) return UNKNOWN_INVOICE;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/invoices/{invoice_id}/payment", { params: { path: { invoice_id: invoiceId } }, body: { paid } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: paid ? "Factura marcada como cobrada." : "Factura marcada como pendiente de cobro." };
  }
  refresh();
  return { status: "error", message: problemOf(result.response, result.error).message };
}

/** «Generar PDF» de una factura que aún no lo tiene. Idempotente en el servidor; puede tardar unos segundos. */
export async function generateInvoicePdf(invoiceId: string): Promise<FormState> {
  if (!isInvoiceId(invoiceId)) return UNKNOWN_INVOICE;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/invoices/{invoice_id}/pdf", { params: { path: { invoice_id: invoiceId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: "PDF generado. Ya puedes descargarlo." };
  }
  const problem = problemOf(result.response, result.error);
  refresh();
  return { status: "error", message: problem.message };
}
