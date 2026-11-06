// POST /gastos/<id>/leer: comprueba el archivo subido y lo lee (complete_document_upload). Espera al agente hasta 45 s.
import { handleRead } from "@/lib/read-handler";

export const maxDuration = 60; // 45 s de lectura + comprobaciones

export async function POST(request: Request, context: RouteContext<"/gastos/[id]/leer">) {
  const { id } = await context.params;
  return handleRead(request, id, "complete");
}
