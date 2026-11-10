import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { InvoiceDocument } from "@/components/invoices/invoice-detail";
import { KindBadge, PaymentBadge } from "@/components/invoices/invoice-badges";
import { PaymentButton } from "@/components/invoices/payment-button";
import { PdfActions } from "@/components/invoices/pdf-actions";
import { RectifyForm } from "@/components/invoices/rectify-form";
import { madridToday } from "@/lib/invoices";
import { getInvoice } from "@/lib/invoices-api";
import { formatCents } from "@/lib/money";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Factura" };

export default async function FacturaPage(props: PageProps<"/facturas/[id]">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const { id } = await props.params;
  const params = await props.searchParams;
  const invoice = await getInvoice(id);
  if (!invoice) notFound(); // también si es de otra persona: la API no lo distingue
  const rectifying = invoice.kind === "rectifying";
  const issued = params["emitida"] === "1";
  // Solo se rectifica una ordinaria a la que le queda base vigente; el servidor vuelve a comprobarlo.
  const canRectify = !rectifying && invoice.standing !== null && invoice.standing.base_cents > 0;

  return (
    <>
      <p className="mb-3 text-[15px]">
        <Link href="/facturas" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          ← Volver a Facturas
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
        <PdfActions invoiceId={invoice.id} ready={invoice.pdf_status === "ready"} />
      </header>

      {issued ? (
        <p role="status" className="mb-4 rounded-md border border-status-ok bg-status-ok-bg px-3 py-2.5 text-[15px] font-semibold text-status-ok">
          {rectifying ? "Rectificativa" : "Factura"} {invoice.display_number} emitida.
          {invoice.pdf_status === "pending" ? " El PDF no se ha podido preparar todavía: pulsa «Generar PDF»." : ""}
        </p>
      ) : null}

      <div className="grid gap-6">
        <InvoiceDocument invoice={invoice} />

        <p className="text-sm text-ink-soft">
          {rectifying
            ? "Emitida y bloqueada. Una rectificativa no se corrige: si tiene un error, rectifica la factura original."
            : "Emitida y bloqueada. Para corregirla, emite una rectificativa."}
        </p>

        {!rectifying ? (
          <section aria-labelledby="cobro" className="grid gap-2">
            <h2 id="cobro" className="text-base">
              Cobro
            </h2>
            <PaymentButton invoiceId={invoice.id} paid={invoice.paid_at !== null} />
          </section>
        ) : null}

        {canRectify && invoice.standing ? (
          <RectifyForm
            invoiceId={invoice.id}
            displayNumber={invoice.display_number}
            standingLabel={formatCents(invoice.standing.base_cents)}
            today={madridToday(new Date())}
          />
        ) : null}
      </div>
    </>
  );
}
