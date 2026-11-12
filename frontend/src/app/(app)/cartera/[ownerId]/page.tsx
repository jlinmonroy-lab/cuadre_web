import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FichaTabs } from "@/components/cartera/ficha-tabs";
import { DocumentsTab, ExpensesTab, InvoicesTab, NotesTab, ProfileTab, TaxesTab } from "@/components/cartera/ficha-tabs-content";
import { PendingMarker } from "@/components/cartera/portfolio";
import { isOwnerId, parseTab } from "@/lib/gestor-cartera";
import { getAutonomo } from "@/lib/gestor-reads-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Ficha del autónomo" };

export default async function FichaPage(props: PageProps<"/cartera/[ownerId]">) {
  await requireRole("gestor"); // el autónomo y el administrador van a /403; la API vuelve a decidirlo
  const { ownerId } = await props.params;
  if (!isOwnerId(ownerId)) notFound(); // un id que no es un UUID ni llega a la API
  const params = await props.searchParams;
  const tab = parseTab(params); // `?tab=`: una pestaña de la lista; lo demás es Facturas
  const autonomo = await getAutonomo(ownerId);
  if (!autonomo) notFound(); // sin vínculo, revocado, de otro gestor o inexistente: la API contesta lo mismo

  return (
    <>
      <p className="mb-3 text-[15px]">
        <Link href="/cartera" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          ← Volver a la cartera
        </Link>
      </p>
      <header className="mb-5 grid gap-1">
        <h1 className="[overflow-wrap:anywhere]">{autonomo.name}</h1>
        <p className="text-ink-soft [overflow-wrap:anywhere]">{autonomo.email}</p>
        <PendingMarker count={autonomo.pending_count} />
        <p className="mt-1 max-w-[70ch] text-[13px] text-ink-soft">Solo consulta: no puedes emitir, registrar ni cambiar nada de este autónomo. Lo que miras queda anotado para él.</p>
      </header>
      <div className="grid gap-6">
        <FichaTabs ownerId={ownerId} current={tab} />
        {tab === "facturas" ? <InvoicesTab ownerId={ownerId} params={params} /> : null}
        {tab === "gastos" ? <ExpensesTab ownerId={ownerId} params={params} /> : null}
        {tab === "documentos" ? <DocumentsTab ownerId={ownerId} /> : null}
        {tab === "trimestres" ? <TaxesTab ownerId={ownerId} params={params} /> : null}
        {tab === "perfil" ? <ProfileTab ownerId={ownerId} /> : null}
        {tab === "anotaciones" ? <NotesTab ownerId={ownerId} /> : null}
      </div>
    </>
  );
}
