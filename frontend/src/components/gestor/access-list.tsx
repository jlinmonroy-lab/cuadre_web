"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import { Feedback } from "@/components/gestor/feedback";
import { TAG } from "@/components/scope-badge";
import { Button } from "@/components/ui/button";
import { initialFormState, type FormState } from "@/lib/form-state";
import { revokeGestorAccess } from "@/lib/gestor-actions";
import { STATUS_LABEL, STATUS_TONE, accessDetail, canRevoke, formatWhen, type GestorAccess, type Tone } from "@/lib/gestor";

// El estado siempre va escrito; el color solo lo refuerza.
const TONE_STYLE: Record<Tone, string> = {
  ok: "bg-status-ok-bg text-status-ok",
  wait: "bg-status-doubt-bg text-status-doubt",
  closed: "bg-muted text-ink-soft",
};

/**
 * «Revocar»: pide una confirmación en la misma fila (sin diálogos del navegador). Al abrirla el foco pasa al botón de confirmar; «Escape» o
 * «Cancelar» la cierran y el foco vuelve a «Revocar». El servidor decide si se puede; la interfaz solo ofrece el botón a lo que está abierto.
 */
function RevokeAccess({ access }: { access: GestorAccess }) {
  const [confirming, setConfirming] = useState(false);
  const revokeRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  // «Revocar» no está montado mientras se confirma: el foco se le devuelve cuando vuelve a pintarse, no al pedir cancelar.
  const refocusRevoke = useRef(false);
  const [state, action, pending] = useActionState(async (): Promise<FormState> => {
    const next = await revokeGestorAccess(access.id);
    if (next.status === "sent") setConfirming(false);
    return next;
  }, initialFormState);

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
    else if (refocusRevoke.current) {
      refocusRevoke.current = false;
      revokeRef.current?.focus();
    }
  }, [confirming]);

  const cancel = () => {
    refocusRevoke.current = true;
    setConfirming(false);
  };

  return (
    <div className="grid gap-2">
      {confirming ? (
        <form
          action={action}
          role="group"
          aria-label={`Confirmar la revocación del acceso de ${access.gestor_email}`}
          onKeyDown={(event) => {
            if (event.key === "Escape") cancel();
          }}
          className="grid gap-2 rounded-md border border-status-error bg-status-error-bg p-3"
        >
          <p className="text-[14px] font-semibold text-status-error [overflow-wrap:anywhere]">
            ¿Revocar el acceso de {access.gestor_email}? Dejará de ver tu contabilidad al instante.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button ref={confirmRef} type="submit" variant="destructive" size="sm" disabled={pending}>
              {pending ? "Revocando…" : "Sí, revocar"}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={cancel} disabled={pending}>
              Cancelar
            </Button>
          </div>
        </form>
      ) : (
        <Button
          ref={revokeRef}
          type="button"
          variant="outline"
          size="sm"
          aria-label={`Revocar el acceso de ${access.gestor_email}`}
          onClick={() => setConfirming(true)}
        >
          Revocar
        </Button>
      )}
      <Feedback state={state} />
    </div>
  );
}

/** Cada acceso con su estado en texto. Los cerrados (rechazados, revocados y caducados) se quedan en la lista como historial. */
export function AccessList({ accesses }: { accesses: GestorAccess[] }) {
  if (accesses.length === 0) return <p className="text-ink-soft">Todavía no has invitado a nadie.</p>;
  return (
    <ul className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]">
      {accesses.map((access) => (
        <li key={access.id} className="grid content-start gap-2 rounded-panel border border-rule bg-sheet p-4">
          <p className="font-semibold [overflow-wrap:anywhere]">{access.gestor_email}</p>
          <p>
            <span className={`${TAG} ${TONE_STYLE[STATUS_TONE[access.status]]}`}>
              <span className="sr-only">Estado: </span>
              {STATUS_LABEL[access.status]}
            </span>
          </p>
          <p className="text-[13px] text-ink-soft">
            {accessDetail(access) ? `${accessDetail(access)} · ` : ""}Invitado el {formatWhen(access.invited_at)}
          </p>
          {canRevoke(access.status) ? <RevokeAccess access={access} /> : null}
        </li>
      ))}
    </ul>
  );
}
