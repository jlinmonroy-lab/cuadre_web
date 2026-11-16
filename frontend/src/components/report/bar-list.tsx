import type { ReactNode } from "react";

import { formatCents } from "@/lib/money";
import { barPercent } from "@/lib/report";

export type Bar = { key: string; label: ReactNode; cents: number; tone: string };

/**
 * Barras horizontales: una fila por elemento con su etiqueta y su importe escritos y, debajo, la barra (decorativa). La escala es la del mayor importe
 * positivo; un importe negativo (una rectificativa) no dibuja barra y se escribe con su signo.
 */
export function BarList({ bars, empty }: { bars: Bar[]; empty: string }) {
  if (bars.length === 0) return <p className="text-ink-soft">{empty}</p>;
  const max = bars.reduce((top, bar) => Math.max(top, bar.cents), 0);
  return (
    <ul className="m-0 grid list-none gap-3 p-0">
      {bars.map((bar) => (
        <li key={bar.key} className="grid gap-1">
          <div className="flex items-baseline justify-between gap-3 text-[15px]">
            <span className="[overflow-wrap:anywhere]">{bar.label}</span>
            <span className="font-semibold tabular-nums whitespace-nowrap">{formatCents(bar.cents)}</span>
          </div>
          <div aria-hidden="true" className="h-2.5 overflow-hidden rounded-full bg-muted">
            <div className={`h-full rounded-full ${bar.tone}`} style={{ width: `${barPercent(bar.cents, max)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
