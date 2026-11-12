import type { Metadata } from "next";

import { InvitationList } from "@/components/cartera/invitations";
import { Portfolio } from "@/components/cartera/portfolio";
import { getPortfolio, listInvitations } from "@/lib/gestor-reads-api";
import { roleLabel } from "@/lib/roles";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Cartera" };

export default async function CarteraPage() {
  const me = await requireRole("gestor"); // el autónomo y el administrador van a /403; la API vuelve a decidirlo
  const [portfolio, invitations] = await Promise.all([getPortfolio(), listInvitations()]);
  const firstName = me.display_name.trim().split(/\s+/)[0] ?? "";

  return (
    <>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>Hola, {firstName || me.email}</h1>
          <p className="mt-1 max-w-[70ch] text-ink-soft">
            Consultas la contabilidad de los autónomos que te dan acceso. Solo lees y dejas anotaciones: no emites ni registras nada por ellos, y cada vez que consultas algo
            queda anotado para el autónomo.
          </p>
        </div>
        <span className="rounded-full bg-action-soft px-2.5 py-0.5 text-[13px] font-semibold whitespace-nowrap text-action-hover">{roleLabel(me.role)}</span>
      </header>
      <div className="grid gap-8">
        {invitations.length > 0 ? (
          <section aria-labelledby="invitaciones" className="grid gap-3">
            <h2 id="invitaciones" className="text-lg">
              Invitaciones recibidas
            </h2>
            <p className="max-w-[70ch] text-[13px] text-ink-soft">No verás nada del autónomo hasta que aceptes su invitación.</p>
            <InvitationList invitations={invitations} />
          </section>
        ) : null}
        <section aria-labelledby="cartera" className="grid gap-3">
          <h2 id="cartera" className="text-lg">
            Tu cartera
          </h2>
          <Portfolio entries={portfolio} />
        </section>
      </div>
    </>
  );
}
