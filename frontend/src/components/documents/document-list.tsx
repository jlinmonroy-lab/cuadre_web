import { CircleAlert, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/documents/status-badge";
import { docTypeLabel, formatMoment } from "@/lib/documents";
import type { DocumentSummary } from "@/lib/documents-api";
import { formatCents } from "@/lib/money";

/**
 * Lista de documentos en tarjetas apiladas, no en tabla: a 390 px una tabla obligaría a desplazarse en horizontal (T2-11).
 * Todo lo que viene del agente (proveedor, nombre) se pinta como texto: React lo escapa y nunca se interpreta.
 */
export function DocumentList({ documents }: { documents: DocumentSummary[] }) {
  if (documents.length === 0) {
    return (
      <p className="rounded-panel border border-rule bg-sheet px-5 py-8 text-center text-ink-soft">
        Todavía no has subido ninguna factura de compra. Cuando subas una, aparecerá aquí con su estado.
      </p>
    );
  }
  return (
    <ul className="grid gap-3">
      {documents.map((document) => (
        <li key={document.id}>
          <DocumentCard document={document} />
        </li>
      ))}
    </ul>
  );
}

function DocumentCard({ document }: { document: DocumentSummary }) {
  const title = document.supplier_name ?? document.original_filename;
  return (
    <article className="relative grid gap-2 rounded-panel border border-rule bg-sheet p-4 transition-colors hover:border-rule-strong hover:bg-white sm:grid-cols-[1fr_auto] sm:items-start sm:gap-x-6">
      <div className="grid min-w-0 gap-1.5">
        <h3 className="text-[15px] leading-snug font-bold">
          {/* El enlace cubre toda la tarjeta (::after), pero su nombre accesible es solo el título. */}
          <Link href={`/gastos/${document.id}`} className="[overflow-wrap:anywhere] after:absolute after:inset-0 after:content-['']">
            {title}
          </Link>
        </h3>
        {document.supplier_name ? <p className="text-[13px] text-ink-soft [overflow-wrap:anywhere]">{document.original_filename}</p> : null}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <StatusBadge status={document.status} doubtfulCount={document.doubtful_count} />
          {document.injection_suspected ? (
            <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-status-doubt">
              <ShieldAlert aria-hidden="true" className="size-3.5 shrink-0" />
              Revísalo con cuidado
            </span>
          ) : null}
          <span className="text-[13px] text-ink-soft">
            {document.doc_type ? `${docTypeLabel(document.doc_type)} · ` : ""}Subido {formatMoment(document.created_at)}
          </span>
        </div>
        {document.error ? (
          <p className="flex items-start gap-1.5 text-[13px] text-status-error">
            <CircleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            <span>{document.error.message}</span>
          </p>
        ) : null}
      </div>
      <p className="text-lg font-bold tabular-nums sm:text-right">{formatCents(document.total_cents)}</p>
    </article>
  );
}
