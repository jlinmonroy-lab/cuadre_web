import { SCOPE_STYLE, TAG } from "@/components/scope-badge";
import { CLIENT_KINDS, countryName, taxIdLabel } from "@/lib/countries";
import type { OwnerClient } from "@/lib/gestor-reads-api";
import { SCOPE_LABEL } from "@/lib/invoices";

// El ámbito y el estado de VIES los calcula el servidor: aquí solo se muestran, siempre como TEXTO (el color solo refuerza).
const VIES: Record<OwnerClient["vies_status"], { label: string; style: string }> = {
  valid_simulated: { label: "Válido (simulado)", style: "bg-status-ok-bg text-status-ok" },
  unchecked: { label: "Sin comprobar", style: "bg-status-doubt-bg text-status-doubt" },
  not_applicable: { label: "No aplica", style: "bg-muted text-ink-soft" },
};

const kindLabel = (kind: OwnerClient["kind"]): string => CLIENT_KINDS.find((option) => option.value === kind)?.label ?? kind;

/** Los clientes de un autónomo, en lectura (los archivados, marcados con texto). Sin acciones: el gestor no edita ni archiva nada. */
export function OwnerClients({ clients }: { clients: OwnerClient[] }) {
  if (clients.length === 0) return <p className="text-ink-soft">Todavía no tiene clientes.</p>;
  return (
    <ul className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]">
      {clients.map((client) => (
        <li key={client.id} className="grid content-start gap-1.5 rounded-panel border border-rule bg-sheet p-4">
          <h3 className="text-[15px] leading-snug [overflow-wrap:anywhere]">{client.name}</h3>
          <p className="text-[13px] text-ink-soft">
            {kindLabel(client.kind)} · {countryName(client.country)}
          </p>
          <p className="text-[13px] text-ink-soft">
            {taxIdLabel(client.country, client.kind).label}: <span className="font-semibold text-ink [overflow-wrap:anywhere]">{client.tax_id ?? "—"}</span>
          </p>
          {client.address ? <p className="text-[13px] text-ink-soft [overflow-wrap:anywhere]">{client.address}</p> : null}
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label="Ámbito y comprobación de VIES">
            <li className={`${TAG} ${SCOPE_STYLE[client.scope]}`}>{SCOPE_LABEL[client.scope]}</li>
            <li className={`${TAG} ${VIES[client.vies_status].style}`}>
              <span className="sr-only">VIES: </span>
              {VIES[client.vies_status].label}
            </li>
            {client.archived ? <li className={`${TAG} bg-muted text-ink-soft`}>Archivado</li> : null}
          </ul>
        </li>
      ))}
    </ul>
  );
}
