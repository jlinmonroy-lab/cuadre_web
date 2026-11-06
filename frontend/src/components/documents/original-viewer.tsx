import { ExternalLink } from "lucide-react";

import { quoteName } from "@/lib/documents";

/**
 * El documento original, para compararlo con lo leído. Apunta a `/gastos/<id>/original`, que redirige a una URL firmada NUEVA cada
 * vez (la de Storage caduca a los 60 s y la persona tarda más en revisar). Las imágenes van en `<img>`; el PDF, en un `<iframe>`
 * (según el navegador puede no pintarse, por eso el enlace para abrirlo siempre está debajo); HEIC no se puede mostrar.
 */
export function OriginalViewer({ documentId, mimeType, filename }: { documentId: string; mimeType: string; filename: string }) {
  const src = `/gastos/${documentId}/original`;
  const title = `Documento original ${quoteName(filename)}`;
  return (
    <section aria-labelledby="original-titulo" id="original" className="grid content-start gap-3 min-[1280px]:sticky min-[1280px]:top-6">
      <h2 id="original-titulo">Documento original</h2>
      {mimeType === "application/pdf" ? (
        <iframe src={src} title={title} className="h-[70dvh] min-h-80 w-full rounded-panel border border-rule bg-white" />
      ) : mimeType === "image/heic" ? (
        <p className="rounded-panel border border-rule bg-sheet px-4 py-6 text-ink-soft">
          Este formato (HEIC) no se puede mostrar en el navegador. Ábrelo o descárgalo con el enlace de abajo para compararlo con los datos.
        </p>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- imagen del usuario servida por una URL firmada que cambia en cada vista: `next/image` no aporta nada
        <img src={src} alt={title} loading="lazy" decoding="async" className="max-h-[70dvh] w-full rounded-panel border border-rule bg-white object-contain" />
      )}
      <p>
        <a
          href={src}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 font-semibold text-action underline underline-offset-2 hover:text-action-hover"
        >
          {mimeType === "image/heic" ? "Abrir o descargar el original" : "Abrir el original en otra pestaña"}
          <ExternalLink aria-hidden="true" className="size-4" />
        </a>
      </p>
    </section>
  );
}
