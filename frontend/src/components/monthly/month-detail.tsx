import { MonthStatusBadge } from "@/components/monthly/month-status";
import { ScopeBadge } from "@/components/scope-badge";
import { formatCents } from "@/lib/money";
import { closingNote, monthTitle, type MonthlyClosing } from "@/lib/monthly";

const NUM = "tabular-nums text-right whitespace-nowrap";

/**
 * El detalle de un mes: de dónde vienen los ingresos (por cliente, con su ámbito), el resultado y la nota de cierre. Los importes son los del servidor, también
 * el resultado del mes; los ingresos son bases imponibles, sin IVA.
 */
export function MonthDetail({ detail }: { detail: MonthlyClosing }) {
  const title = `${monthTitle(detail.month)} de ${detail.year}`;
  return (
    <section aria-labelledby="mes-elegido" className="grid gap-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 id="mes-elegido" className="text-base">
          {title}
        </h2>
        <MonthStatusBadge status={detail.status} />
      </div>
      <div className="grid gap-4 min-[900px]:grid-cols-2">
        <section aria-labelledby="mes-clientes" className="grid content-start gap-3 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
          <h3 id="mes-clientes">Ingresos por cliente</h3>
          {detail.by_client.length === 0 ? (
            <p className="text-ink-soft">No hay facturas emitidas este mes.</p>
          ) : (
            <table className="w-full border-collapse text-left text-[15px]">
              <caption className="sr-only">Ingresos de {title} por cliente</caption>
              <thead className="sr-only">
                <tr>
                  <th scope="col">Cliente</th>
                  <th scope="col">Ámbito</th>
                  <th scope="col">Base imponible</th>
                </tr>
              </thead>
              <tbody>
                {detail.by_client.map((client) => (
                  <tr key={`${client.client_id}-${client.scope}`} className="border-b border-rule align-top">
                    <th scope="row" className="py-2 pr-3 font-normal [overflow-wrap:anywhere]">
                      {client.name}
                    </th>
                    <td className="py-2 pr-3">
                      <ScopeBadge scope={client.scope} />
                    </td>
                    <td className={`${NUM} py-2`}>{formatCents(client.base_cents)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold">
                  <th scope="row" className="py-2 pr-3 text-left">
                    Total
                  </th>
                  <td />
                  <td className={`${NUM} py-2`}>{formatCents(detail.total_cents)}</td>
                </tr>
              </tfoot>
            </table>
          )}
        </section>

        <section aria-labelledby="mes-resultado" className="grid content-start gap-3 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
          <h3 id="mes-resultado">Resultado de {monthTitle(detail.month).toLowerCase()}</h3>
          <table className="w-full border-collapse text-left text-[15px]">
            <caption className="sr-only">Resultado de {title}</caption>
            <tbody>
              <tr className="border-b border-rule">
                <th scope="row" className="py-2 pr-3 font-normal">
                  Ingresos
                </th>
                <td className={`${NUM} py-2`}>{formatCents(detail.total_cents)}</td>
              </tr>
              <tr className="border-b border-rule">
                <th scope="row" className="py-2 pr-3 font-normal">
                  Gastos deducibles
                </th>
                <td className={`${NUM} py-2`}>{formatCents(detail.expenses_cents)}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr className="font-semibold">
                <th scope="row" className="py-2 pr-3 text-left">
                  Rendimiento del mes
                </th>
                <td className={`${NUM} py-2`}>{formatCents(detail.result_cents)}</td>
              </tr>
            </tfoot>
          </table>
          <p className="text-[13px] text-ink-soft">{closingNote(detail, detail.year)}</p>
        </section>
      </div>
    </section>
  );
}
