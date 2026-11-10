import type { Metadata } from "next";

import { InvoiceFilters } from "@/components/invoices/invoice-filters";
import { NewInvoice } from "@/components/invoices/invoice-form";
import { InvoiceList } from "@/components/invoices/invoice-list";
import { CompleteProfileNotice } from "@/components/profile/complete-profile-notice";
import { listClients } from "@/lib/clients-api";
import { madridToday, parseListQuery } from "@/lib/invoices";
import { listInvoices } from "@/lib/invoices-api";
import { getProfileForNotice, listInvoiceSeries } from "@/lib/profile-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Facturas" };

export default async function FacturasPage(props: PageProps<"/facturas">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  const today = madridToday(new Date());
  const currentYear = Number(today.slice(0, 4));
  // Los filtros viven en la dirección (`?year=&scope=&paid=`): es una lectura de servidor, sin estado en el navegador.
  const query = parseListQuery(params, currentYear);
  const [invoices, clients, series, profile] = await Promise.all([listInvoices(query), listClients(false), listInvoiceSeries(), getProfileForNotice()]);
  const filtered = query.scope !== undefined || query.paid !== undefined;
  const canIssue = profile === null || profile.completeness.can_issue; // sin perfil legible no se bloquea: la API decide al emitir

  return (
    <>
      <header className="mb-6">
        <h1>Facturas</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          Una factura emitida no se edita ni se borra: si hay un error, se corrige con una factura rectificativa.
        </p>
      </header>
      <div className="grid gap-6">
        {canIssue ? (
          <NewInvoice
            clients={clients.map((client) => ({ id: client.id, name: client.name, hasAddress: Boolean(client.address) }))}
            series={series.filter((item) => !item.archived).map((item) => ({ id: item.id, code: item.code, isDefault: item.is_default }))}
            today={today}
          />
        ) : profile ? (
          <CompleteProfileNotice missing={profile.completeness.missing_for_invoicing} />
        ) : null}
        <InvoiceFilters query={query} currentYear={currentYear} />
        <section aria-labelledby="facturas-del-anio" className="grid gap-3">
          <h2 id="facturas-del-anio" className="text-base">
            Facturas de {query.year}
          </h2>
          <InvoiceList
            invoices={invoices}
            empty={filtered ? "No hay facturas con estos filtros." : `Todavía no has emitido facturas en ${query.year}.`}
          />
        </section>
      </div>
    </>
  );
}
