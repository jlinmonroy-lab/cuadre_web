import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { NoteForm } from "@/components/cartera/note-form";
import { KindBadge, PaymentBadge } from "@/components/invoices/invoice-badges";
import { InvoiceDocument } from "@/components/invoices/invoice-detail";
import { buttonVariants } from "@/components/ui/button";
import { fichaHref, invoiceDetailHref, invoicePdfHref, isOwnerId } from "@/lib/gestor-cartera";
import { getOwnerInvoice } from "@/lib/gestor-reads-api";
import { isUuid } from "@/lib/gestor";
import { formatCents } from "@/lib/money";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Factura del autónomo" };

export default async function OwnerInvoicePage(props: PageProps<"/cartera/[ownerId]/facturas/[id]">) {
  await requireRole("gestor"); // el autónomo y el administrador van a /403; la API vuelve a decidirlo
  const { ownerId, id } = await props.params;
  if (!isOwnerId(ownerId) || !isUuid(id)) notFound();
  const invoice = await getOwnerInvoice(ownerId, id);
  if (!invoice) notFound(); // sin vínculo, de otro autónomo o inexistente: la API contesta lo mismo
  const rectifying = invoice.kind === "rectifying";

  return (
    <>
      <p className="mb-3 text-[15px]">
        <Link href={fichaHref(ownerId, "facturas")} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          ← Volver a las facturas del autónomo
        </Link>
      </p>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <h1>
            {rectifying ? "Rectificativa" : "Factura"} {invoice.display_number}
          </h1>
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Estado">
            <li>{rectifying ? <KindBadge invoice={invoice} /> : <PaymentBadge invoice={invoice} />}</li>
          </ul>
        </div>
        {/* `<a>` normal: sin precarga (cada pulsación es una lectura registrada). El gestor nunca genera el PDF: solo lo descarga si ya existe. */}
        {invoice.pdf_status === "ready" ? (
          <a href={invoicePdfHref(ownerId, invoice.id)} className={buttonVariants({ variant: "default" })}>
            Descargar PDF
          </a>
        ) : (
          <p className="text-[13px] text-ink-soft">Esta factura aún no tiene PDF.</p>
        )}
      </header>

      <div className="grid gap-6">
        <InvoiceDocument invoice={invoice} invoiceHref={(rectifiedId) => invoiceDetailHref(ownerId, rectifiedId)} />
        <p className="text-sm text-ink-soft">Emitida y bloqueada: una factura emitida no se edita ni se borra. Tú solo la consultas.</p>
        {!rectifying && invoice.standing !== null ? (
          <p className="text-sm text-ink-soft">
            Base vigente: <strong className="text-ink">{formatCents(invoice.standing.base_cents)}</strong>.
          </p>
        ) : null}
        <section aria-labelledby="anotar-factura" className="grid gap-3">
          <h2 id="anotar-factura" className="text-base">
            Anotar sobre esta factura
          </h2>
          <NoteForm ownerId={ownerId} invoiceId={invoice.id} title="Anotación sobre esta factura" />
        </section>
      </div>
    </>
  );
}
