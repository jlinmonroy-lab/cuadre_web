import { SCOPE_LABEL, type Scope } from "@/lib/invoices";

/** Clases de una insignia de texto (el color solo refuerza: el estado siempre va escrito). */
export const TAG = "inline-block rounded-full px-2.5 py-0.5 text-[13px] font-semibold";

// El ámbito lo calcula el servidor: aquí solo se muestra, siempre como TEXTO.
export const SCOPE_STYLE: Record<Scope, string> = {
  national: "bg-muted text-ink",
  eu: "bg-scope-eu-bg text-scope-eu",
  non_eu: "bg-scope-non-eu-bg text-scope-non-eu",
};

/** Insignia del ámbito del cliente (Nacional, UE, Fuera de la UE), la misma en Clientes y en Facturas. */
export function ScopeBadge({ scope }: { scope: Scope }) {
  return <span className={`${TAG} ${SCOPE_STYLE[scope]}`}>{SCOPE_LABEL[scope]}</span>;
}
