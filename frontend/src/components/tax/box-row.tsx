import Link from "next/link";

import { boxView303, type Box303, type BoxLineView } from "@/lib/tax";

/**
 * Una casilla de la hoja, ya escrita (`BoxLineView`): su número, su nombre, su importe y, si la componen documentos, un desplegable nativo con
 * ellos (cada factura enlaza a su detalle; los gastos, a la lista de Gastos; el 130 enlaza también cada trimestre anterior a su propio 130). Las
 * casillas derivadas dicen de cuáles se componen. Es el marcado de los dos modelos; sin JavaScript de cliente.
 */
export function BoxLine({ view }: { view: BoxLineView }) {
  return (
    <li className="grid grid-cols-[2.75rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-b border-dotted border-rule py-1.5 last:border-b-0">
      <span
        className={`rounded-[2px] border border-ink py-px text-center text-xs font-bold tabular-nums ${view.isResult ? "bg-ink text-sheet" : "bg-paper"}`}
      >
        <span className="sr-only">Casilla </span>
        {view.code}
      </span>
      <span>
        {view.label}
        {view.derived ? <span className="block text-[13px] text-ink-soft">{view.derived}</span> : null}
      </span>
      <span
        className={`min-w-28 bg-sheet px-2 py-0.5 text-right font-semibold tabular-nums ${view.isResult ? "border-2 border-ink" : "border border-rule-strong"}`}
      >
        {view.amount}
      </span>
      {view.summary ? (
        <details className="col-span-full text-[13px] text-ink-soft min-[480px]:col-start-2">
          <summary className="w-max cursor-pointer font-semibold text-action hover:text-action-hover">{view.summary}</summary>
          <ul className="mt-2 grid list-none gap-1 p-0 pl-1">
            {view.items.map((item) => (
              <li key={item.key} className="flex flex-wrap gap-x-2">
                {item.href ? (
                  <Link href={item.href} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                    {item.label}
                  </Link>
                ) : (
                  <span className="font-semibold text-ink">{item.label}</span>
                )}
                <span>{item.date}</span>
                <span className="tabular-nums">{item.amount}</span>
              </li>
            ))}
            {view.expensesLink ? (
              <li>
                <Link href="/gastos" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                  Ir a Gastos
                </Link>
              </li>
            ) : null}
          </ul>
        </details>
      ) : null}
    </li>
  );
}

/** Una casilla del 303. */
export function BoxRow({ box }: { box: Box303 }) {
  return <BoxLine view={boxView303(box)} />;
}
