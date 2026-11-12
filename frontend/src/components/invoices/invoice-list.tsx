import Link from "next/link";

import { KindBadge, PaymentBadge } from "@/components/invoices/invoice-badges";
import { ScopeBadge } from "@/components/scope-badge";
import { formatDate, retentionText, vatText, type Invoice } from "@/lib/invoices";
import { formatCents } from "@/lib/money";

const NUM = "tabular-nums text-right whitespace-nowrap";
const ownerInvoiceHref = (id: string): string => `/facturas/${id}`;

/** A dónde lleva el número de una factura (por defecto, su detalle del autónomo; la ficha del gestor pasa el suyo). */
export type InvoiceHref = (id: string) => string;

function InvoiceCard({ invoice, invoiceHref }: { invoice: Invoice; invoiceHref: InvoiceHref }) {
  return (
    <article className="grid gap-3 rounded-panel border border-rule bg-sheet p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <h3 className="text-[15px] leading-snug">
          <Link href={invoiceHref(invoice.id)} className="text-action underline underline-offset-2 hover:text-action-hover">
            <span className="sr-only">Factura </span>
            {invoice.display_number}
          </Link>
        </h3>
        <p className="text-[13px] text-ink-soft">{formatDate(invoice.issue_date)}</p>
      </div>
      <p className="[overflow-wrap:anywhere]">{invoice.client.name}</p>
      <ul className="flex flex-wrap gap-1.5" aria-label="Ámbito y estado">
        <li>
          <ScopeBadge scope={invoice.client.scope} />
        </li>
        {invoice.kind === "rectifying" ? (
          <li>
            <KindBadge invoice={invoice} />
          </li>
        ) : (
          <li>
            <PaymentBadge invoice={invoice} />
          </li>
        )}
      </ul>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[15px]">
        <dt className="text-ink-soft">Base</dt>
        <dd className={NUM}>{formatCents(invoice.base_cents)}</dd>
        <dt className="text-ink-soft">IVA</dt>
        <dd className={NUM}>{vatText(invoice)}</dd>
        <dt className="text-ink-soft">Retención</dt>
        <dd className={NUM}>{retentionText(invoice)}</dd>
        <dt className="font-semibold">Total</dt>
        <dd className={`${NUM} font-bold`}>{formatCents(invoice.total_cents)}</dd>
      </dl>
    </article>
  );
}

/**
 * Facturas del año: tarjetas apiladas hasta 1.279 px y tabla desde 1.280 (como Clientes y Gastos). Las dos vistas están en el DOM y solo una se
 * muestra (la otra va con `display: none`, así que no existe para el lector de pantalla). Es un Server Component: los importes y las fechas ya
 * salen formateados del servidor, así que no hay nada que hidratar.
 */
export function InvoiceList({ invoices, empty, invoiceHref = ownerInvoiceHref }: { invoices: Invoice[]; empty: string; invoiceHref?: InvoiceHref }) {
  if (invoices.length === 0) {
    return <p className="rounded-panel border border-rule bg-sheet px-5 py-6 text-center text-ink-soft">{empty}</p>;
  }
  return (
    <>
      <ul className="grid gap-3 min-[1280px]:hidden">
        {invoices.map((invoice) => (
          <li key={invoice.id}>
            <InvoiceCard invoice={invoice} invoiceHref={invoiceHref} />
          </li>
        ))}
      </ul>

      <div className="hidden min-[1280px]:block">
        <table className="w-full border-collapse text-left text-[15px]">
          <caption className="sr-only">Facturas del año, de la más reciente a la más antigua</caption>
          <thead>
            <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
              <th scope="col" className="py-2 pr-4 font-semibold">
                Número
              </th>
              <th scope="col" className="py-2 pr-4 font-semibold">
                Fecha
              </th>
              <th scope="col" className="py-2 pr-4 font-semibold">
                Cliente
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Base
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                IVA
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Retención
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Total
              </th>
              <th scope="col" className="py-2 pr-4 font-semibold">
                Cobro
              </th>
              <th scope="col" className="py-2 font-semibold">
                Ámbito
              </th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="border-b border-rule align-top hover:bg-sheet">
                <th scope="row" className="py-3 pr-4 font-bold whitespace-nowrap">
                  <Link href={invoiceHref(invoice.id)} className="text-action underline underline-offset-2 hover:text-action-hover">
                    {invoice.display_number}
                  </Link>
                  {invoice.kind === "rectifying" ? (
                    <span className="mt-1 block font-normal">
                      <KindBadge invoice={invoice} />
                    </span>
                  ) : null}
                </th>
                <td className="py-3 pr-4 whitespace-nowrap">{formatDate(invoice.issue_date)}</td>
                <td className="py-3 pr-4 [overflow-wrap:anywhere]">{invoice.client.name}</td>
                <td className={`${NUM} py-3 pr-4`}>{formatCents(invoice.base_cents)}</td>
                <td className={`${NUM} py-3 pr-4`}>{vatText(invoice)}</td>
                <td className={`${NUM} py-3 pr-4`}>{retentionText(invoice)}</td>
                <td className={`${NUM} py-3 pr-4 font-bold`}>{formatCents(invoice.total_cents)}</td>
                <td className="py-3 pr-4">{invoice.kind === "rectifying" ? <span className="text-ink-soft">—</span> : <PaymentBadge invoice={invoice} />}</td>
                <td className="py-3">
                  <ScopeBadge scope={invoice.client.scope} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
