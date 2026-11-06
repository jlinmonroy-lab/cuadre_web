import { ArrowLeft, CircleAlert, LoaderCircle, ShieldAlert, TriangleAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AutoRefresh } from "@/components/documents/auto-refresh";
import { DiscardButton } from "@/components/documents/discard-button";
import { OriginalViewer } from "@/components/documents/original-viewer";
import { RereadButton } from "@/components/documents/reread-button";
import { ReviewForm } from "@/components/documents/review-form";
import { StatusBadge } from "@/components/documents/status-badge";
import { getDocument } from "@/lib/documents-api";
import { failureHint, formatMoment } from "@/lib/documents";
import { initialValues } from "@/lib/review";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Revisar gasto" };

export default async function DocumentPage(props: PageProps<"/gastos/[id]">) {
  await requireRole("usuario");
  const { id } = await props.params;
  const document = await getDocument(id);
  if (!document) notFound();

  const doubts = document.extraction?.doubtful_fields ?? [];
  const reviewable = document.status === "review" || document.status === "extraction_failed";
  const hasFile = document.status !== "uploading";
  // Si la lectura termina o se vuelve a pedir, el formulario se vuelve a montar con los datos nuevos; guardar correcciones no lo cambia.
  const formKey = `${document.status}-${document.extracted_at ?? "sin-lectura"}`;

  return (
    <>
      <header className="mb-6 grid gap-2">
        <Link href="/gastos" className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Gastos
        </Link>
        <h1 className="[overflow-wrap:anywhere]">{document.original_filename}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <StatusBadge status={document.status} doubtfulCount={doubts.length} />
          <span className="text-[13px] text-ink-soft">Subido {formatMoment(document.uploaded_at ?? document.created_at)}</span>
        </div>
      </header>

      <div className="grid gap-6">
        {document.injection_suspected ? (
          <div className="flex items-start gap-3 rounded-md border border-status-doubt-line bg-status-doubt-bg px-4 py-3 text-status-doubt">
            <ShieldAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
            <div className="grid gap-0.5">
              <p className="font-semibold">Este documento contiene texto que parece una instrucción dirigida a un sistema automático.</p>
              <p className="text-sm">Se ha ignorado, pero conviene que revises todos los datos con atención antes de fiarte de ellos.</p>
            </div>
          </div>
        ) : null}

        {document.status === "processing" ? (
          <div role="status" className="flex items-start gap-3 rounded-panel border border-rule bg-sheet px-5 py-4">
            <LoaderCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0 animate-spin motion-reduce:animate-none" />
            <div className="grid gap-0.5">
              <p className="font-semibold">Leyendo el documento…</p>
              <p className="text-sm text-ink-soft">Suele tardar unos segundos. Esta pantalla se actualiza sola cuando termine.</p>
            </div>
          </div>
        ) : null}

        {document.status === "uploading" ? (
          <div className="grid gap-3 rounded-panel border border-rule bg-sheet px-5 py-4">
            <p className="font-semibold">Este documento no ha terminado de subirse.</p>
            <p className="text-sm text-ink-soft">Si la subida se interrumpió, descártalo y vuelve a subirlo desde Gastos.</p>
            <div>
              <DiscardButton documentId={document.id} />
            </div>
          </div>
        ) : null}

        {document.status === "processing" ? (
          <div>
            <DiscardButton documentId={document.id} />
          </div>
        ) : null}

        {document.status === "extraction_failed" && document.error ? (
          <div role="alert" className="flex items-start gap-3 rounded-md border border-status-error bg-status-error-bg px-4 py-3 text-status-error">
            <CircleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
            <div className="grid gap-0.5">
              <p className="font-semibold">{document.error.message}</p>
              {failureHint(document.error.code) ? <p className="text-sm">{failureHint(document.error.code)}</p> : null}
            </div>
          </div>
        ) : null}

        {document.status === "review" && doubts.length > 0 ? (
          <p className="flex items-start gap-2 rounded-md border border-status-doubt-line bg-status-doubt-bg px-4 py-3 text-sm font-semibold text-status-doubt">
            <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>
              {doubts.length === 1 ? "Hay 1 dato dudoso" : `Hay ${doubts.length} datos dudosos`}: compruébalo{doubts.length === 1 ? "" : "s"} con el documento original antes de guardar.{" "}
              <a href="#original" className="underline underline-offset-2 min-[1280px]:hidden">
                Ir al original
              </a>
            </span>
          </p>
        ) : null}

        {document.extraction && document.extraction.warnings.length > 0 ? (
          <section aria-labelledby="avisos-titulo" className="grid gap-1.5 rounded-md border border-rule-strong bg-muted px-4 py-3">
            <h2 id="avisos-titulo" className="text-[15px]">
              Avisos de la lectura
            </h2>
            {/* Texto del agente: se pinta como texto, nunca como HTML ni como orden. */}
            <ul className="list-disc pl-5 text-sm">
              {document.extraction.warnings.map((warning, index) => (
                <li key={index} className="[overflow-wrap:anywhere]">
                  {warning}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <div className={hasFile && reviewable ? "grid items-start gap-8 min-[1280px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" : "grid gap-8"}>
          {reviewable ? (
            <section aria-labelledby="datos-titulo" className="grid min-w-0 gap-4">
              <h2 id="datos-titulo">Datos de la factura</h2>
              <ReviewForm
                key={formKey}
                documentId={document.id}
                initial={initialValues({ extraction: document.extraction, review: document.review })}
                doubts={doubts}
                actions={
                  <>
                    <RereadButton documentId={document.id} />
                    <DiscardButton documentId={document.id} />
                  </>
                }
              />
            </section>
          ) : null}
          {hasFile ? <OriginalViewer documentId={document.id} mimeType={document.mime_type} filename={document.original_filename} /> : null}
        </div>
      </div>

      <AutoRefresh active={document.status === "processing"} />
    </>
  );
}
