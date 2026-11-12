// GET /cartera/<owner>/facturas/<id>/pdf: el PDF de una factura de un autónomo, por URL firmada de corta vida (la lectura queda registrada). Ver `handleGestorDownload`.
import { handleGestorDownload } from "@/lib/gestor-routes";

export async function GET(_request: Request, context: RouteContext<"/cartera/[ownerId]/facturas/[id]/pdf">) {
  const { ownerId, id } = await context.params;
  return handleGestorDownload("pdf", ownerId, id);
}
