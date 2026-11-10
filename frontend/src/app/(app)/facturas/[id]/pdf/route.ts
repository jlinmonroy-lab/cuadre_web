// GET /facturas/<id>/pdf: descarga el PDF de una factura propia (get_invoice_pdf). Ver `handleInvoicePdf`.
import { handleInvoicePdf } from "@/lib/invoice-routes";

export async function GET(_request: Request, context: RouteContext<"/facturas/[id]/pdf">) {
  const { id } = await context.params;
  return handleInvoicePdf(id);
}
