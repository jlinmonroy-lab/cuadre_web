import { ScopeBadge } from "@/components/scope-badge";
import { formatCents } from "@/lib/money";
import { formatBp, type ScopeShare } from "@/lib/report";

/** El color de la barra de cada ámbito: los mismos del resto de la aplicación. La barra es decorativa; la leyenda lo dice todo con texto. */
export const SCOPE_BAR: Record<ScopeShare["scope"], string> = { national: "bg-action", eu: "bg-scope-eu", non_eu: "bg-scope-non-eu" };

/**
 * El reparto de los ingresos del mes por ámbito: una barra segmentada (el ancho de cada tramo es su base en céntimos enteros, solo las positivas) y una
 * leyenda con el ámbito, el importe y la cuota que calculó el servidor. Sin ingresos positivos no hay barra.
 */
export function ScopeBar({ scopes }: { scopes: ScopeShare[] }) {
  const drawn = scopes.filter((scope) => scope.base_cents > 0);
  return (
    <div className="grid gap-3">
      {drawn.length === 0 ? (
        <p className="text-ink-soft">Este mes no hay ingresos positivos que repartir entre ámbitos.</p>
      ) : (
        <div aria-hidden="true" className="flex h-3 overflow-hidden rounded-full bg-muted">
          {drawn.map((scope) => (
            <div key={scope.scope} className={SCOPE_BAR[scope.scope]} style={{ flexGrow: scope.base_cents, flexBasis: 0 }} />
          ))}
        </div>
      )}
      <ul className="m-0 grid list-none gap-1.5 p-0 text-[15px]">
        {scopes.map((scope) => (
          <li key={scope.scope} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2">
              <span aria-hidden="true" className={`inline-block size-2.5 rounded-sm ${SCOPE_BAR[scope.scope]}`} />
              <ScopeBadge scope={scope.scope} />
            </span>
            <span className="tabular-nums whitespace-nowrap">
              <span className="font-semibold">{formatCents(scope.base_cents)}</span>
              {scope.share_bp === null ? null : <span className="text-ink-soft"> · {formatBp(scope.share_bp)}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
