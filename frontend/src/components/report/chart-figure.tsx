import type { ReactNode } from "react";

/**
 * El contenedor común de un gráfico del reporte: título, el dibujo con su texto alternativo (`role="img"` y un resumen con las mismas cifras) y la tabla
 * equivalente, plegada en un `<details>` nativo (sin JavaScript). Nada se dice solo con el color: cada barra lleva su etiqueta y su importe escritos.
 */
export function ChartFigure({ id, title, summary, children, table }: { id: string; title: string; summary: string; children: ReactNode; table: ReactNode }) {
  return (
    <figure aria-labelledby={`${id}-titulo`} className="m-0 grid content-start gap-3 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
      <figcaption id={`${id}-titulo`} className="text-base font-semibold">
        {title}
      </figcaption>
      <div role="img" aria-label={summary}>
        {children}
      </div>
      <details className="text-[14px]">
        <summary className="w-fit cursor-pointer font-semibold text-action underline underline-offset-2 hover:text-action-hover">Ver como tabla</summary>
        <div className="mt-3">{table}</div>
      </details>
    </figure>
  );
}

const NUM = "tabular-nums text-right whitespace-nowrap";

export type TableRow = { key: string; cells: ReactNode[]; current?: boolean };

/** La tabla equivalente de un gráfico: la primera columna es el encabezado de fila y las demás, números. */
export function DataTable({ caption, head, rows }: { caption: string; head: string[]; rows: TableRow[] }) {
  return (
    <table className="w-full border-collapse text-left text-[14px]">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-rule-strong text-ink-soft">
          {head.map((cell, index) => (
            <th key={cell} scope="col" className={`py-1.5 font-semibold ${index === 0 ? "pr-3" : `pl-3 ${NUM}`}`}>
              {cell}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className="border-b border-rule align-top" aria-current={row.current ? "true" : undefined}>
            {row.cells.map((cell, index) =>
              index === 0 ? (
                <th key={index} scope="row" className="py-1.5 pr-3 font-normal [overflow-wrap:anywhere]">
                  {cell}
                </th>
              ) : (
                <td key={index} className={`py-1.5 pl-3 ${NUM}`}>
                  {cell}
                </td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
