"use client";

import { useActionState } from "react";

import { Feedback } from "@/components/gestor/feedback";
import { Button } from "@/components/ui/button";
import { acceptInvitation, declineInvitation } from "@/lib/gestor-cartera-actions";
import { invitationExpiry, type GestorInvitation } from "@/lib/gestor-cartera";
import { initialFormState } from "@/lib/form-state";

/**
 * Una invitación recibida: quién invita y cuándo caduca, con «Aceptar» y «Rechazar». El gestor no puede ver nada del autónomo hasta aceptar. El resultado
 * se anuncia (`aria-live`); al aceptar o rechazar la lista se recarga y la tarjeta desaparece.
 */
function InvitationCard({ invitation }: { invitation: GestorInvitation }) {
  const [acceptState, accept, accepting] = useActionState(async () => acceptInvitation(invitation.id), initialFormState);
  const [declineState, decline, declining] = useActionState(async () => declineInvitation(invitation.id), initialFormState);
  const busy = accepting || declining;
  const state = declineState.status !== "idle" ? declineState : acceptState;
  return (
    <li className="grid content-start gap-3 rounded-panel border border-rule bg-sheet p-4">
      <div className="grid gap-0.5">
        <p className="font-semibold [overflow-wrap:anywhere]">{invitation.owner_name}</p>
        <p className="text-[13px] text-ink-soft">{invitationExpiry(invitation.expires_at)}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <form action={accept}>
          <Button type="submit" size="sm" disabled={busy} aria-label={`Aceptar la invitación de ${invitation.owner_name}`}>
            {accepting ? "Aceptando…" : "Aceptar"}
          </Button>
        </form>
        <form action={decline}>
          <Button type="submit" size="sm" variant="outline" disabled={busy} aria-label={`Rechazar la invitación de ${invitation.owner_name}`}>
            {declining ? "Rechazando…" : "Rechazar"}
          </Button>
        </form>
      </div>
      <Feedback state={state} />
    </li>
  );
}

export function InvitationList({ invitations }: { invitations: GestorInvitation[] }) {
  return (
    <ul className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]">
      {invitations.map((invitation) => (
        <InvitationCard key={invitation.id} invitation={invitation} />
      ))}
    </ul>
  );
}
