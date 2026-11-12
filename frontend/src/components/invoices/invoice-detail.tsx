import Link from "next/link";

import { ScopeBadge } from "@/components/scope-badge";
import { countryName, taxIdLabel } from "@/lib/countries";
import { formatLongDate, rateText, retentionText, type Invoice } from "@/lib/invoices";
import { formatCents } from "@/lib/money";

const NUM = "tabular-nums text-right whitespace-nowrap";

function Party({ title, name, taxIdLine, address, country }: { title: string; name: string; taxIdLine: string | null; address: string; country?: string }) {
  return (
    <div className="grid content-start gap-0.5">
      <h3 className="mb-1 text-[13px] font-semibold tracking-wide text-ink-soft uppercase">{title}</h3>
      <p className="font-semibold [overflow-wrap:anywhere]">{name}</p>
      {taxIdLine ? <p className="[overflow-wrap:anywhere]">{taxIdLine}</p> : null}
      <p className="text-ink-soft [overflow-wrap:anywhere]">{address}</p>
      {country ? <p className="text-ink-soft">{country}</p> : null}
    </div>
  );
}

/**
 * La factura como documento (lo que lleva su PDF): emisora y cliente con las COPIAS que congeló al emitirse, el concepto, los importes, la mención
 * legal y la relación con sus rectificativas. Todo viene de la API; aquí no se calcula nada.
 */
export function InvoiceDocument({ invoice, invoiceHref = (id) => `/facturas/${id}` }: { invoice: Invoice; invoiceHref?: (id: string) => string }) {
  const { client, issuer } = invoice;
  const noVat = Number(invoice.vat_rate) === 0;
  const rectifying = invoice.kind === "rectifying";
  return (
    <article aria-labelledby="documento" className="grid gap-5 rounded-panel border border-rule bg-sheet p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div>
          <h2 id="documento" className="text-xl">
            {rectifying ? "Factura rectificativa" : "Factura"} {invoice.display_number}
          </h2>
          <p className="text-ink-soft">Fecha de expedición: {formatLongDate(invoice.issue_date)}</p>
        </div>
        <ScopeBadge scope={client.scope} />
      </header>

      {invoice.rectifies ? (
        <p className="rounded-md bg-muted px-3 py-2 text-[15px]">
          Rectifica la factura{" "}
          <Link href={invoiceHref(invoice.rectifies.id)} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
            {invoice.rectifies.display_number}
          </Link>{" "}
          del {formatLongDate(invoice.rectifies.issue_date)}.
          {invoice.rectification_reason ? <span className="block [overflow-wrap:anywhere]">Motivo: {invoice.rectification_reason}</span> : null}
        </p>
      ) : null}

      <div className="grid gap-5 sm:grid-cols-2">
        <Party title="Emisora" name={issuer.name} taxIdLine={`NIF ${issuer.tax_id}`} address={issuer.address} />
        <Party
          title="Cliente"
          name={client.name}
          taxIdLine={client.tax_id ? `${taxIdLabel(client.country, client.kind).label} ${client.tax_id}` : null}
          address={client.address}
          country={countryName(client.country)}
        />
      </div>

      <table className="w-full border-collapse text-left text-[15px]">
        <caption className="sr-only">Importes de la factura {invoice.display_number}</caption>
        <thead>
          <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
            <th scope="col" className="py-2 pr-4 font-semibold">
              Concepto
            </th>
            <th scope="col" className="py-2 text-right font-semibold">
              Importe
            </th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-rule">
            <td className="py-3 pr-4 [overflow-wrap:anywhere]">{invoice.concept}</td>
            <td className={`${NUM} py-3`}>{formatCents(invoice.base_cents)}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" className="pt-3 pr-4 font-normal">
              Base imponible
            </th>
            <td className={`${NUM} pt-3`}>{formatCents(invoice.base_cents)}</td>
          </tr>
          <tr>
            <th scope="row" className="pt-1 pr-4 font-normal">
              {noVat ? "IVA" : `IVA ${rateText(invoice.vat_rate)} %`}
            </th>
            <td className={`${NUM} pt-1`}>{noVat ? "Sin IVA" : formatCents(invoice.vat_cents)}</td>
          </tr>
          {invoice.irpf_cents !== 0 ? (
            <tr>
              <th scope="row" className="pt-1 pr-4 font-normal">
                Retención de IRPF {rateText(invoice.irpf_rate)} %
              </th>
              <td className={`${NUM} pt-1`}>{retentionText(invoice)}</td>
            </tr>
          ) : null}
          <tr className="text-base font-bold">
            <th scope="row" className="pt-2 pr-4">
              Total
            </th>
            <td className={`${NUM} pt-2`}>{formatCents(invoice.total_cents)}</td>
          </tr>
        </tfoot>
      </table>

      {invoice.legal_note ? <p className="rounded-md bg-status-doubt-bg px-3 py-2 text-[15px] text-status-doubt">{invoice.legal_note}</p> : null}

      {invoice.rectified_by.length > 0 ? (
        <p className="text-[15px]">
          <strong className="font-semibold">Rectificada por:</strong> {invoice.rectified_by.join(", ")}.
          {invoice.standing ? <span className="block text-ink-soft">Base vigente tras las rectificativas: {formatCents(invoice.standing.base_cents)}.</span> : null}
        </p>
      ) : null}
    </article>
  );
}
