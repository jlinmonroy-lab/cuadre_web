import Link from "next/link";

import { MonthStatusBadge } from "@/components/monthly/month-status";
import { formatCents } from "@/lib/money";
import { monthHref, monthTitle, type MonthRow, type MonthlyClosings } from "@/lib/monthly";

const NUM = "tabular-nums text-right whitespace-nowrap";

function MonthCard({ year, row, selected }: { year: number; row: MonthRow; selected: boolean }) {
  return (
    <article className={`grid gap-3 rounded-panel border bg-sheet p-4 ${selected ? "border-ink" : "border-rule"}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <h3 className="text-[15px] leading-snug">
          <Link href={monthHref(year, row.month)} aria-current={selected ? "true" : undefined} className="text-action underline underline-offset-2 hover:text-action-hover">
            {monthTitle(row.month)}
            <span className="sr-only"> de {year}: ver el detalle</span>
          </Link>
        </h3>
        <MonthStatusBadge status={row.status} />
      </div>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[15px]">
        <dt className="text-ink-soft">Facturas</dt>
        <dd className={NUM}>{row.invoice_count}</dd>
        <dt className="text-ink-soft">Nacional</dt>
        <dd className={NUM}>{formatCents(row.national_cents)}</dd>
        <dt className="text-ink-soft">UE</dt>
        <dd className={NUM}>{formatCents(row.eu_cents)}</dd>
        <dt className="text-ink-soft">Fuera de la UE</dt>
        <dd className={NUM}>{formatCents(row.non_eu_cents)}</dd>
        <dt className="font-semibold">Total del mes</dt>
        <dd className={`${NUM} font-bold`}>{formatCents(row.total_cents)}</dd>
        <dt className="text-ink-soft">Gastos</dt>
        <dd className={NUM}>{formatCents(row.expenses_cents)}</dd>
        <dt className="text-ink-soft">Acumulado del año</dt>
        <dd className={NUM}>{formatCents(row.ytd_cents)}</dd>
      </dl>
    </article>
  );
}

/**
 * Los meses del año. Por debajo de 1280 px, una tarjeta por mes (sin scroll horizontal); desde ahí, la tabla del prototipo. Cada mes es un enlace al
 * detalle (`?anio=&mes=`). Todas las cifras son las que manda el servidor, también el acumulado y el total del año.
 */
export function MonthsTable({ data, selected }: { data: MonthlyClosings; selected: number | null }) {
  const { year, months, totals } = data;
  if (months.length === 0) {
    return <p className="rounded-panel border border-rule bg-sheet px-5 py-6 text-center text-ink-soft">No hay meses que mostrar en {year}: tu actividad empieza después.</p>;
  }
  return (
    <>
      <ul className="grid gap-3 min-[1280px]:hidden">
        {months.map((row) => (
          <li key={row.month}>
            <MonthCard year={year} row={row} selected={row.month === selected} />
          </li>
        ))}
        <li className="rounded-panel border border-rule bg-paper p-4">
          <p className="font-semibold">Total {year}</p>
          <p className="mt-1 tabular-nums">
            {totals.invoice_count} facturas · {formatCents(totals.total_cents)} de ingresos · {formatCents(totals.expenses_cents)} de gastos
          </p>
        </li>
      </ul>

      <div className="hidden min-[1280px]:block">
        <table className="w-full border-collapse text-left text-[15px]">
          <caption className="sr-only">Meses de {year} con sus ingresos por ámbito, sus gastos y el acumulado del año</caption>
          <thead>
            <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
              <th scope="col" className="py-2 pr-4 font-semibold">
                Mes
              </th>
              <th scope="col" className="py-2 pr-4 font-semibold">
                Estado
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Facturas
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Nacional
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                UE
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Fuera de la UE
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Total del mes
              </th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">
                Gastos
              </th>
              <th scope="col" className="py-2 text-right font-semibold">
                Acumulado del año
              </th>
            </tr>
          </thead>
          <tbody>
            {months.map((row) => {
              const isSelected = row.month === selected;
              return (
                <tr key={row.month} className={`border-b border-rule align-top ${isSelected ? "bg-paper" : "hover:bg-sheet"}`}>
                  <th scope="row" className="py-3 pr-4 font-bold whitespace-nowrap">
                    <Link href={monthHref(year, row.month)} aria-current={isSelected ? "true" : undefined} className="text-action underline underline-offset-2 hover:text-action-hover">
                      {monthTitle(row.month)}
                      <span className="sr-only"> de {year}: ver el detalle</span>
                    </Link>
                  </th>
                  <td className="py-3 pr-4">
                    <MonthStatusBadge status={row.status} />
                  </td>
                  <td className={`${NUM} py-3 pr-4`}>{row.invoice_count}</td>
                  <td className={`${NUM} py-3 pr-4`}>{formatCents(row.national_cents)}</td>
                  <td className={`${NUM} py-3 pr-4`}>{formatCents(row.eu_cents)}</td>
                  <td className={`${NUM} py-3 pr-4`}>{formatCents(row.non_eu_cents)}</td>
                  <td className={`${NUM} py-3 pr-4 font-bold`}>{formatCents(row.total_cents)}</td>
                  <td className={`${NUM} py-3 pr-4`}>{formatCents(row.expenses_cents)}</td>
                  <td className={`${NUM} py-3`}>{formatCents(row.ytd_cents)}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-rule-strong font-semibold">
              <th scope="row" className="py-3 pr-4 text-left">
                Total {year}
              </th>
              <td className="py-3 pr-4" />
              <td className={`${NUM} py-3 pr-4`}>{totals.invoice_count}</td>
              <td className={`${NUM} py-3 pr-4`}>{formatCents(totals.national_cents)}</td>
              <td className={`${NUM} py-3 pr-4`}>{formatCents(totals.eu_cents)}</td>
              <td className={`${NUM} py-3 pr-4`}>{formatCents(totals.non_eu_cents)}</td>
              <td className={`${NUM} py-3 pr-4`}>{formatCents(totals.total_cents)}</td>
              <td className={`${NUM} py-3 pr-4`}>{formatCents(totals.expenses_cents)}</td>
              <td className="py-3" />
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
