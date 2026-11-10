import type { Metadata } from "next";
import Link from "next/link";

import { AddClient } from "@/components/clients/client-form";
import { ClientList } from "@/components/clients/client-list";
import { CountriesProvider } from "@/components/clients/countries-context";
import { listClients } from "@/lib/clients-api";
import { sortedCountries } from "@/lib/countries";
import { madridToday } from "@/lib/invoices";
import { getBilledByClient, getClientConditions } from "@/lib/invoices-api";
import { formatCents } from "@/lib/money";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Clientes" };

export default async function ClientesPage(props: PageProps<"/clientes">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  // Los archivados se piden por la dirección (`?archivados=1`): es una lectura de servidor, sin estado en el navegador.
  const showArchived = params["archivados"] === "1";
  const clients = await listClients(showArchived);
  // Lo facturado en el año y las condiciones de facturación de cada cliente salen de la API (facturas y vista previa): la web no calcula nada.
  const year = Number(madridToday(new Date()).slice(0, 4));
  const [billedCents, conditions] = await Promise.all([getBilledByClient(year), getClientConditions(clients)]);
  const billing = {
    year,
    billed: Object.fromEntries(clients.map((client) => [client.id, formatCents(billedCents.get(client.id) ?? 0)])),
    conditions: Object.fromEntries(conditions),
  };

  return (
    <>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <h1>Clientes</h1>
          <p className="mt-1 max-w-[70ch] text-ink-soft">
            El país y el tipo de cliente deciden cómo se llama su identificador fiscal y cómo se trata en tus facturas: nacional, de la UE o de fuera de
            la UE. Lo calcula la aplicación; tú solo eliges el país.
          </p>
        </div>
        <Link
          href={showArchived ? "/clientes" : "/clientes?archivados=1"}
          className="text-[15px] font-semibold text-action underline underline-offset-2 hover:text-action-hover"
        >
          {showArchived ? "Ocultar archivados" : "Mostrar archivados"}
        </Link>
      </header>
      {/* Los nombres de país se calculan AQUÍ, en el servidor, y viajan hasta el selector y la lista: cada motor nombra y ordena distinto algunos
          códigos, y si se calcularan en el navegador la hidratación no coincidiría con el HTML (React #418). */}
      <CountriesProvider countries={sortedCountries()}>
        <div className="grid gap-6">
          <AddClient />
          <ClientList clients={clients} showArchived={showArchived} billing={billing} />
          <p className="max-w-[70ch] text-[13px] text-ink-soft">Los NIF-IVA de la UE se comprueban en VIES (simulado en esta versión).</p>
        </div>
      </CountriesProvider>
    </>
  );
}
