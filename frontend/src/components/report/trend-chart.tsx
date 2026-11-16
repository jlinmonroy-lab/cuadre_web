import { columnPercents, shortMonth, trendStatus, type TrendPoint } from "@/lib/report";

/**
 * La evolución de los últimos meses: dos columnas por mes (ingresos y gastos) con una escala común, la etiqueta del mes debajo y, para el mes elegido, un marco
 * y una marca escrita. La leyenda es de texto; los importes de cada mes están en la tabla equivalente.
 */
export function TrendChart({ trend, year, month }: { trend: TrendPoint[]; year: number; month: number }) {
  const columns = columnPercents(trend);
  return (
    <div className="grid gap-3">
      <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[14px]">
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block size-2.5 rounded-sm bg-action" /> Ingresos (base imponible)
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block size-2.5 rounded-sm bg-scope-non-eu" /> Gastos
        </li>
      </ul>
      <ol className="m-0 grid list-none gap-1 p-0" style={{ gridTemplateColumns: `repeat(${trend.length}, minmax(0, 1fr))` }}>
        {trend.map((point, index) => {
          const selected = point.year === year && point.month === month;
          const column = columns[index];
          return (
            <li
              key={`${point.year}-${point.month}`}
              title={`${shortMonth(point.month)} ${point.year}: ${trendStatus(point)}`}
              className={`grid grid-rows-[8rem_auto] gap-1 rounded-md px-0.5 pb-1 ${selected ? "bg-action-soft ring-1 ring-action" : ""}`}
            >
              <div aria-hidden="true" className="flex items-end justify-center gap-0.5 border-b border-rule-strong">
                <div className="w-1/2 max-w-5 rounded-t-sm bg-action" style={{ height: `${column?.income ?? 0}%` }} />
                <div className="w-1/2 max-w-5 rounded-t-sm bg-scope-non-eu" style={{ height: `${column?.expenses ?? 0}%` }} />
              </div>
              <span className={`text-center text-[11px] leading-tight sm:text-[12px] ${selected ? "font-bold text-ink" : "text-ink-soft"}`}>
                {shortMonth(point.month)}
                {selected ? <span className="sr-only"> (mes del reporte)</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
