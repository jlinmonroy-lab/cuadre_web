// El contenido de cada pestaña de la ficha del gestor. Son Server Components: cada uno lee lo suyo con la sesión del gestor y, si la API contesta el `404`
// uniforme (sin vínculo, revocado, de otro gestor o inexistente), la página dice «no encontrado». Todo es de solo lectura: ningún botón de emitir, registrar,
// editar ni archivar. Los datos y los enlaces vienen del servidor; aquí solo se ordenan y se escriben.
import Link from "next/link";
import { notFound } from "next/navigation";

import { DocumentList } from "@/components/documents/document-list";
import { ExpenseList } from "@/components/expenses/expense-list";
import { NoteForm } from "@/components/cartera/note-form";
import { OwnerClients } from "@/components/cartera/owner-clients";
import { OwnerProfile } from "@/components/cartera/owner-profile";
import { NotesList } from "@/components/gestor/notes-list";
import { InvoiceFilters } from "@/components/invoices/invoice-filters";
import { InvoiceList } from "@/components/invoices/invoice-list";
import { DeadlineStatus } from "@/components/tax/deadline-status";
import { Modelo130Sheet } from "@/components/tax/modelo-130";
import { Modelo303Sheet } from "@/components/tax/modelo-303";
import { TaxNotes } from "@/components/tax/notes";
import { QuarterPicker } from "@/components/tax/quarter-picker";
import { cursorParam } from "@/lib/expenses";
import {
  documentOriginalHref,
  expensesHref,
  gestorNoteLinks,
  gestorTaxLinks,
  invoiceDetailHref,
  invoicesHref,
  parsePage,
  quarterTabHref,
  splitPage,
} from "@/lib/gestor-cartera";
import {
  getOwnerModelo130,
  getOwnerModelo303,
  getOwnerProfile,
  listOwnerClients,
  listOwnerDocuments,
  listOwnerExpenses,
  listOwnerInvoices,
  listOwnerNotes,
} from "@/lib/gestor-reads-api";
import { madridToday, parseListQuery } from "@/lib/invoices";
import type { Modelo130, Modelo303 } from "@/lib/tax";
import { parseModel, parseQuarterQuery, quarterEnabled, quarterMonths, quarterOfDate, quarterTitle } from "@/lib/tax";

type Params = Record<string, string | string[] | undefined>;
const LINK = "font-semibold text-action underline underline-offset-2 hover:text-action-hover";

export async function InvoicesTab({ ownerId, params }: { ownerId: string; params: Params }) {
  const today = madridToday(new Date());
  const currentYear = Number(today.slice(0, 4));
  // Los filtros y la página viven en la dirección (`?year=&scope=&paid=&pagina=`): es una lectura de servidor, sin estado en el navegador.
  const query = parseListQuery(params, currentYear);
  const page = parsePage(params);
  const rows = await listOwnerInvoices(ownerId, query, page);
  if (rows === null) notFound();
  const { items, hasNext } = splitPage(rows);
  const filtered = query.scope !== undefined || query.paid !== undefined;
  return (
    <div className="grid gap-4">
      <InvoiceFilters query={query} currentYear={currentYear} action={`/cartera/${ownerId}`} hidden={{ tab: "facturas" }} />
      <section aria-labelledby="facturas-del-anio" className="grid gap-3">
        <h2 id="facturas-del-anio" className="text-base">
          Facturas de {query.year}
        </h2>
        <InvoiceList
          invoices={items}
          invoiceHref={(id) => invoiceDetailHref(ownerId, id)}
          empty={page > 1 ? "No hay más facturas." : filtered ? "No hay facturas con estos filtros." : `No hay facturas emitidas en ${query.year}.`}
        />
        {page > 1 || hasNext ? (
          <nav aria-label="Páginas de facturas" className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[15px]">
            {page > 1 ? (
              <Link href={invoicesHref(ownerId, query, page - 1, currentYear)} className={LINK}>
                Página anterior
              </Link>
            ) : null}
            <span className="text-ink-soft">Página {page}</span>
            {hasNext ? (
              <Link href={invoicesHref(ownerId, query, page + 1, currentYear)} className={LINK}>
                Página siguiente
              </Link>
            ) : null}
          </nav>
        ) : null}
      </section>
    </div>
  );
}

export async function ExpensesTab({ ownerId, params }: { ownerId: string; params: Params }) {
  const cursor = cursorParam(Array.isArray(params["cursor"]) ? params["cursor"][0] : params["cursor"]);
  const result = await listOwnerExpenses(ownerId, cursor);
  if (result === null) notFound();
  return (
    <section aria-labelledby="gastos-registrados" className="grid gap-3">
      <h2 id="gastos-registrados" className="text-base">
        Gastos registrados
      </h2>
      <p className="max-w-[70ch] text-[13px] text-ink-soft">Los gastos anulados se enseñan marcados: ya no cuentan en las cuentas del autónomo.</p>
      <ExpenseList
        expenses={result.items}
        hrefFor={() => null}
        empty="No hay gastos registrados."
        extraBadges={(expense) => (expense.voided_at !== null ? [{ label: "Anulado", tone: "doubt" }] : [])}
      />
      {cursor || result.next_cursor ? (
        <nav aria-label="Páginas de gastos" className="flex flex-wrap gap-x-6 gap-y-2 text-[15px]">
          {result.next_cursor ? (
            <Link href={expensesHref(ownerId, result.next_cursor)} className={LINK}>
              Ver gastos anteriores
            </Link>
          ) : null}
          {cursor ? (
            <Link href={expensesHref(ownerId)} className={LINK}>
              Volver a los más recientes
            </Link>
          ) : null}
        </nav>
      ) : null}
    </section>
  );
}

export async function DocumentsTab({ ownerId }: { ownerId: string }) {
  const documents = await listOwnerDocuments(ownerId);
  if (documents === null) notFound();
  return (
    <section aria-labelledby="documentos-pendientes" className="grid gap-3">
      <h2 id="documentos-pendientes" className="text-base">
        Documentos para revisar
      </h2>
      <p className="max-w-[70ch] text-[13px] text-ink-soft">Las facturas de compra que el autónomo aún no ha revisado, o que no se han podido leer. Tú solo las consultas.</p>
      <DocumentList
        documents={documents}
        hrefFor={() => null}
        empty="No hay documentos pendientes de revisar."
        extra={(document) => (
          // `<a>` normal y no `Link`: sin precarga (cada pulsación es una lectura registrada) y el archivo se abre en otra pestaña.
          <a href={documentOriginalHref(ownerId, document.id)} target="_blank" rel="noopener noreferrer" className={`${LINK} text-[13px]`}>
            Abrir el original
            <span className="sr-only"> de {document.supplier_name ?? document.original_filename} (se abre en otra pestaña)</span>
          </a>
        )}
      />
    </section>
  );
}

export async function TaxesTab({ ownerId, params }: { ownerId: string; params: Params }) {
  const today = madridToday(new Date());
  // El trimestre y el modelo viven en la dirección (`?model=&year=&quarter=`), como en la pantalla del autónomo.
  const query = parseQuarterQuery(params, today);
  const model = parseModel(params);
  const reading = model === "130" ? await getOwnerModelo130(ownerId, query) : await getOwnerModelo303(ownerId, query);
  if (reading === null) notFound();
  const current = quarterOfDate(today);
  const links = gestorTaxLinks(ownerId);
  return (
    <div className="grid gap-6">
      <QuarterPicker
        year={query.year}
        quarter={query.quarter}
        model={model}
        today={today}
        links={links}
        formAction={`/cartera/${ownerId}`}
        hidden={{ tab: "trimestres" }}
      />
      <section aria-labelledby="trimestre-elegido" className="grid gap-3">
        <h2 id="trimestre-elegido" className="text-base">
          {quarterTitle(query.year, query.quarter)}: {quarterMonths(query.quarter)}
        </h2>
        {reading.status === "ok" ? (
          <>
            <DeadlineStatus model={reading.model} />
            {model === "130" ? (
              <Modelo130Sheet model={reading.model as Modelo130} links={links} />
            ) : (
              <Modelo303Sheet model={reading.model as Modelo303} links={links} />
            )}
            <TaxNotes notes={reading.model.notes} model={model} />
          </>
        ) : (
          <div role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 text-status-doubt">
            <p className="font-semibold">{reading.message}</p>
            <p className="mt-2">
              {quarterEnabled(current.year, current.quarter, today) ? (
                <Link href={quarterTabHref(ownerId, current.year, current.quarter, model)} className="font-semibold underline underline-offset-2">
                  Ir al trimestre actual
                </Link>
              ) : null}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

export async function ProfileTab({ ownerId }: { ownerId: string }) {
  const [view, clients] = await Promise.all([getOwnerProfile(ownerId), listOwnerClients(ownerId)]);
  if (view === null || clients === null) notFound();
  return (
    <div className="grid gap-8">
      <OwnerProfile view={view} />
      <section aria-labelledby="clientes-del-autonomo" className="grid gap-3">
        <h2 id="clientes-del-autonomo" className="text-base">
          Clientes
        </h2>
        <OwnerClients clients={clients} />
      </section>
    </div>
  );
}

export async function NotesTab({ ownerId }: { ownerId: string }) {
  const notes = await listOwnerNotes(ownerId);
  if (notes === null) notFound();
  return (
    <div className="grid gap-6">
      <section aria-labelledby="nueva-anotacion" className="grid gap-3">
        <h2 id="nueva-anotacion" className="text-base">
          Nueva anotación
        </h2>
        <NoteForm ownerId={ownerId} title="Anotación para el autónomo" />
      </section>
      <section aria-labelledby="tus-anotaciones" className="grid gap-3">
        <h2 id="tus-anotaciones" className="text-base">
          Tus anotaciones
        </h2>
        <NotesList notes={notes} links={gestorNoteLinks(ownerId)} empty="Todavía no has dejado ninguna anotación a este autónomo." author="Tú" />
      </section>
    </div>
  );
}
