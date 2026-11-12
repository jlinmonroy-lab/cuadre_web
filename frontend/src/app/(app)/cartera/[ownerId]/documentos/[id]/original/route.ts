// GET /cartera/<owner>/documentos/<id>/original: el archivo original de un documento de un autónomo, por URL firmada de corta vida (la lectura queda registrada). Ver `handleGestorDownload`.
import { handleGestorDownload } from "@/lib/gestor-routes";

export async function GET(_request: Request, context: RouteContext<"/cartera/[ownerId]/documentos/[id]/original">) {
  const { ownerId, id } = await context.params;
  return handleGestorDownload("original", ownerId, id);
}
