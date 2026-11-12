import Link from "next/link";

import { fichaHref, pendingText, type PortfolioEntry } from "@/lib/gestor-cartera";

/** Los pendientes de un autónomo: el número en una marca y también con palabras (el color y el número solos no bastan). Sin pendientes, sin marca. */
export function PendingMarker({ count }: { count: number }) {
  if (!Number.isInteger(count) || count <= 0) return <p className="text-[13px] text-ink-soft">{pendingText(count)}</p>;
  return (
    <p className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-status-doubt-bg text-[13px] font-bold tabular-nums text-status-doubt"
      >
        {count}
      </span>
      <span className="text-[15px] font-semibold text-status-doubt">{pendingText(count)}</span>
    </p>
  );
}

/** La cartera: una tarjeta por autónomo con acceso activo, tal cual la ordena la API (con pendientes primero). Todo se pinta como texto. */
export function Portfolio({ entries }: { entries: PortfolioEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="max-w-3xl rounded-panel border border-rule bg-sheet px-5 py-6 text-ink-soft">
        Todavía no te ha dado acceso ningún autónomo. Cuando alguien te invite, acepta la invitación y aparecerá aquí.
      </p>
    );
  }
  return (
    <ul className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]">
      {entries.map((entry) => (
        <li key={entry.id}>
          <article className="relative grid content-start gap-2 rounded-panel border border-rule bg-sheet p-4 transition-colors hover:border-rule-strong hover:bg-white">
            <h3 className="text-[15px] leading-snug">
              {/* El enlace cubre toda la tarjeta (::after), pero su nombre accesible es solo el nombre del autónomo. */}
              <Link href={fichaHref(entry.id)} className="font-bold [overflow-wrap:anywhere] after:absolute after:inset-0 after:content-['']">
                {entry.name}
              </Link>
            </h3>
            <p className="text-[13px] text-ink-soft [overflow-wrap:anywhere]">{entry.email}</p>
            <PendingMarker count={entry.pending_count} />
          </article>
        </li>
      ))}
    </ul>
  );
}
