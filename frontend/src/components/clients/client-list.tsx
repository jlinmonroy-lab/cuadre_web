"use client";

import { Fragment, useState } from "react";

import { ClientActions, ClientEditor, type ClientRow } from "@/components/clients/client-actions";
import { useCountries } from "@/components/clients/countries-context";
import { CLIENT_KINDS, taxIdLabel } from "@/lib/countries";

const TAG = "inline-block rounded-full px-2.5 py-0.5 text-[13px] font-semibold";

// El ámbito y el estado de VIES los calcula el servidor: aquí solo se muestran, siempre como TEXTO (el color solo refuerza).
const SCOPE: Record<ClientRow["scope"], { label: string; style: string }> = {
  national: { label: "Nacional", style: "bg-muted text-ink" },
  eu: { label: "UE", style: "bg-scope-eu-bg text-scope-eu" },
  non_eu: { label: "Fuera de la UE", style: "bg-scope-non-eu-bg text-scope-non-eu" },
};
const VIES: Record<ClientRow["vies_status"], { label: string; style: string }> = {
  valid_simulated: { label: "Válido (simulado)", style: "bg-status-ok-bg text-status-ok" },
  unchecked: { label: "Sin comprobar", style: "bg-status-doubt-bg text-status-doubt" },
  not_applicable: { label: "No aplica", style: "bg-muted text-ink-soft" },
};

const kindLabel = (kind: ClientRow["kind"]) => CLIENT_KINDS.find((option) => option.value === kind)?.label ?? kind;

function Badges({ client }: { client: ClientRow }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Ámbito y comprobación de VIES">
      <li className={`${TAG} ${SCOPE[client.scope].style}`}>{SCOPE[client.scope].label}</li>
      <li className={`${TAG} ${VIES[client.vies_status].style}`}>
        <span className="sr-only">VIES: </span>
        {VIES[client.vies_status].label}
      </li>
    </ul>
  );
}

function Identifier({ client }: { client: ClientRow }) {
  return client.tax_id ? <span className="[overflow-wrap:anywhere]">{client.tax_id}</span> : <span className="text-ink-soft">Sin identificador</span>;
}

function ClientCard({ client, onNotice }: { client: ClientRow; onNotice: (message: string) => void }) {
  const { nameOf } = useCountries();
  const [editing, setEditing] = useState(false);
  return (
    <article className="grid gap-3 rounded-panel border border-rule bg-sheet p-4">
      <div className="grid gap-1.5">
        <h3 className="text-[15px] leading-snug [overflow-wrap:anywhere]">{client.name}</h3>
        <p className="text-[13px] text-ink-soft">
          {kindLabel(client.kind)} · {nameOf(client.country)}
        </p>
        <p className="text-[13px] text-ink-soft">
          {taxIdLabel(client.country, client.kind).label}: <span className="font-semibold text-ink">{client.tax_id ?? "—"}</span>
        </p>
        <Badges client={client} />
        {client.archived ? <p className="text-[13px] font-semibold text-ink-soft">Archivado</p> : null}
      </div>
      <ClientActions client={client} editing={editing} onToggleEdit={() => setEditing((open) => !open)} onNotice={onNotice} />
      {editing && !client.archived ? <ClientEditor client={client} view="tarjeta" onClose={() => setEditing(false)} /> : null}
    </article>
  );
}

function ClientTableRow({ client, onNotice }: { client: ClientRow; onNotice: (message: string) => void }) {
  const { nameOf } = useCountries();
  const [editing, setEditing] = useState(false);
  return (
    <Fragment>
      <tr className="border-b border-rule align-top hover:bg-sheet">
        <th scope="row" className="py-3 pr-4 font-bold [overflow-wrap:anywhere]">
          {client.name}
          <span className="block text-[13px] font-normal text-ink-soft">
            {kindLabel(client.kind)}
            {client.archived ? " · Archivado" : ""}
          </span>
        </th>
        <td className="py-3 pr-4">
          <Identifier client={client} />
        </td>
        <td className="py-3 pr-4">{nameOf(client.country)}</td>
        <td className="py-3 pr-4">
          <Badges client={client} />
        </td>
        <td className="py-3">
          <ClientActions client={client} editing={editing} onToggleEdit={() => setEditing((open) => !open)} onNotice={onNotice} />
        </td>
      </tr>
      {editing && !client.archived ? (
        <tr className="border-b border-rule">
          <td colSpan={5} className="pb-4 pt-1">
            <ClientEditor client={client} view="tabla" onClose={() => setEditing(false)} />
          </td>
        </tr>
      ) : null}
    </Fragment>
  );
}

/**
 * Clientes: tarjetas apiladas hasta 1.279 px y tabla desde 1.280 (como Gastos, T3-11). Las dos vistas están en el DOM y solo una se muestra (la
 * otra va con `display: none`, así que no existe para el lector de pantalla). La lista llega ordenada por nombre en español desde la API.
 */
export function ClientList({ clients, showArchived }: { clients: ClientRow[]; showArchived: boolean }) {
  // El aviso de «archivado» o «reactivado» vive aquí y no en la fila: al archivar, la fila desaparece de la lista de activos.
  const [notice, setNotice] = useState("");
  return (
    <div className="grid gap-4">
      <p role="status" aria-live="polite" className="min-h-5 text-[13px] font-semibold text-status-ok">
        {notice}
      </p>
      {clients.length === 0 ? (
        <p className="rounded-panel border border-rule bg-sheet px-5 py-6 text-center text-ink-soft">
          {showArchived ? "No tienes clientes." : "Todavía no tienes clientes activos. Añade el primero con «Añadir cliente»."}
        </p>
      ) : (
        <>
          <ul className="grid gap-3 min-[1280px]:hidden">
            {clients.map((client) => (
              <li key={client.id}>
                <ClientCard client={client} onNotice={setNotice} />
              </li>
            ))}
          </ul>

          <div className="hidden min-[1280px]:block">
            <table className="w-full border-collapse text-left text-[15px]">
              <caption className="sr-only">Clientes por nombre</caption>
              <thead>
                <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
                  <th scope="col" className="py-2 pr-4 font-semibold">
                    Cliente
                  </th>
                  <th scope="col" className="w-44 py-2 pr-4 font-semibold">
                    NIF o identificador
                  </th>
                  <th scope="col" className="w-40 py-2 pr-4 font-semibold">
                    País
                  </th>
                  <th scope="col" className="w-72 py-2 pr-4 font-semibold">
                    Ámbito y VIES
                  </th>
                  <th scope="col" className="w-56 py-2 font-semibold">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <ClientTableRow key={client.id} client={client} onNotice={setNotice} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
