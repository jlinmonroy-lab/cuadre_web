// GET /gastos/<id>/original: redirige a una URL firmada nueva del archivo (get_document_preview). Ver `handleOriginal`.
import { handleOriginal } from "@/lib/read-handler";

export async function GET(_request: Request, context: RouteContext<"/gastos/[id]/original">) {
  const { id } = await context.params;
  return handleOriginal(id);
}
