// POST /gastos/<id>/releer: vuelve a leer un documento que falló (retry_document_extraction). Espera al agente hasta 45 s.
import { handleRead } from "@/lib/read-handler";

export const maxDuration = 60;

export async function POST(request: Request, context: RouteContext<"/gastos/[id]/releer">) {
  const { id } = await context.params;
  return handleRead(request, id, "retry");
}
