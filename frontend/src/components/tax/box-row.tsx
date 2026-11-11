import Link from "next/link";

import { formatDate } from "@/lib/invoices";
import { formatCents } from "@/lib/money";
import { componentsText, itemAmount, itemHref, itemSummary, type Box303 } from "@/lib/tax";

/**
 * Una casilla de la hoja: su número, su nombre, su importe y, si la componen documentos, un desplegable nativo con ellos (cada factura
 * enlaza a su detalle; los gastos, a la lista de Gastos). Las casillas derivadas dicen de cuáles se componen. Sin JavaScript de cliente.
 */
export function BoxRow({ box }: { box: Box303 }) {
  const summary = itemSummary(box);
  const derived = componentsText(box);
  const isResult = box.code === "46";
  const hasExpense = box.items.some((item) => item.kind === "expense");
  return (
    <li className="grid grid-cols-[2.75rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-b border-dotted border-rule py-1.5 last:border-b-0">
      <span
        className={`rounded-[2px] border border-ink py-px text-center text-xs font-bold tabular-nums ${isResult ? "bg-ink text-sheet" : "bg-paper"}`}
      >
        <span className="sr-only">Casilla </span>
        {box.code}
      </span>
      <span>
        {box.label}
        {derived ? <span className="block text-[13px] text-ink-soft">{derived}</span> : null}
      </span>
      <span
        className={`min-w-28 bg-sheet px-2 py-0.5 text-right font-semibold tabular-nums ${isResult ? "border-2 border-ink" : "border border-rule-strong"}`}
      >
        {formatCents(box.amount_cents)}
      </span>
      {summary ? (
        <details className="col-span-full text-[13px] text-ink-soft min-[480px]:col-start-2">
          <summary className="w-max cursor-pointer font-semibold text-action hover:text-action-hover">{summary}</summary>
          <ul className="mt-2 grid list-none gap-1 p-0 pl-1">
            {box.items.map((item) => (
              <li key={`${item.kind}-${item.id}`} className="flex flex-wrap gap-x-2">
                {item.kind === "invoice" ? (
                  <Link href={itemHref(item)} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                    {item.label}
                  </Link>
                ) : (
                  <span className="font-semibold text-ink">{item.label}</span>
                )}
                <span>{formatDate(item.date)}</span>
                <span className="tabular-nums">{itemAmount(item, box.measure)}</span>
              </li>
            ))}
            {hasExpense ? (
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
