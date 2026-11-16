import Link from "next/link";

import { SET_ASIDE_NOTE, quarterLinks } from "@/lib/report";

/** Lo que conviene apartar, **sin importe** (D-08): la nota orientativa y los dos borradores del trimestre del mes, donde sí están las casillas. */
export function SetAside({ quarter, quarterYear }: { quarter: number; quarterYear: number }) {
  const links = quarterLinks(quarterYear, quarter);
  const className = "font-semibold text-action underline underline-offset-2 hover:text-action-hover";
  return (
    <section aria-labelledby="reporte-apartar" className="grid content-start gap-3 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
      <h2 id="reporte-apartar" className="text-base">
        Lo que conviene apartar
      </h2>
      <p className="max-w-[70ch] text-[15px] text-ink-soft">{SET_ASIDE_NOTE}</p>
      <ul className="m-0 flex list-none flex-wrap gap-x-6 gap-y-2 p-0">
        <li>
          <Link href={links.modelo303} className={className}>
            Ver el borrador del 303 del T{quarter} de {quarterYear}
          </Link>
        </li>
        <li>
          <Link href={links.modelo130} className={className}>
            Ver el borrador del 130 del T{quarter} de {quarterYear}
          </Link>
        </li>
      </ul>
    </section>
  );
}
