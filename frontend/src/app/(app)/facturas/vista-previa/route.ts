// POST /facturas/vista-previa: lo que se emitiría con lo que lleva escrito el formulario (preview_invoice). Ver `handlePreview`.
import { handlePreview } from "@/lib/invoice-routes";

export async function POST(request: Request) {
  return handlePreview(request);
}
