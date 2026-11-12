import Link from "next/link";

import { describeActivity, formatWhen, type ActivityEntry, type GestorAccess } from "@/lib/gestor";

const LINK = "font-semibold text-action underline underline-offset-2 hover:text-action-hover";

/**
 * El registro de lo que ha pasado con el acceso de tu gestor, lo más reciente primero. Cada frase se redacta en la interfaz (la API solo da
 * el tipo, el id y la fecha: nunca importes ni nombres). Se pagina con enlaces, sin estado en el navegador.
 */
export function ActivityList({
  items,
  accesses,
  nextCursor,
  isFirstPage,
}: {
  items: ActivityEntry[];
  accesses: GestorAccess[];
  nextCursor: string | null;
  isFirstPage: boolean;
}) {
  if (items.length === 0) {
    return <p className="text-ink-soft">{isFirstPage ? "Todavía no hay actividad: aquí verás cuándo tu gestor consulta tu contabilidad." : "No hay más actividad."}</p>;
  }
  return (
    <div className="grid max-w-3xl gap-4">
      <ol className="grid gap-2">
        {items.map((entry) => {
          const line = describeActivity(entry, accesses);
          return (
            <li key={entry.id} className="grid gap-0.5 rounded-md border border-rule bg-sheet px-3 py-2.5">
              <p className="[overflow-wrap:anywhere]">{line.text}</p>
              <p className="text-[13px] text-ink-soft">
                <time dateTime={entry.occurred_at}>{formatWhen(entry.occurred_at)}</time>
                {line.gestor ? <span className="[overflow-wrap:anywhere]"> · {line.gestor}</span> : null}
              </p>
            </li>
          );
        })}
      </ol>
      <nav aria-label="Páginas del registro" className="flex flex-wrap gap-x-6 gap-y-2 text-[15px]">
        {nextCursor ? (
          <Link href={`/gestor?actividad=${nextCursor}`} className={LINK}>
            Ver actividad anterior
          </Link>
        ) : null}
        {!isFirstPage ? (
          <Link href="/gestor" className={LINK}>
            Volver a lo más reciente
          </Link>
        ) : null}
      </nav>
    </div>
  );
}
