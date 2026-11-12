"use client";

import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Feedback } from "@/components/gestor/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { initialFormState } from "@/lib/form-state";
import { inviteGestor } from "@/lib/gestor-actions";

const PREFIX = "gestor";
const FIELD_IDS = { email: `${PREFIX}-email` };

/**
 * «Invitar a tu gestor»: un campo con etiqueta y el error junto a él. La invitación no revela si el correo es de una cuenta (el servidor
 * responde igual en todos los casos), así que tampoco la interfaz lo insinúa. Si el correo no pudo salir, el mensaje lo dice.
 */
export function InviteForm() {
  const [state, action, pending] = useActionState(inviteGestor, initialFormState);
  return (
    <form action={action} noValidate className="grid max-w-xl gap-4 rounded-panel border border-rule bg-sheet p-4">
      <ErrorSummary state={state} fieldIds={FIELD_IDS} />
      <FormRow
        idPrefix={PREFIX}
        name="email"
        label="Correo de tu gestor"
        hint="Le llegará un aviso. Tendrá que aceptar la invitación dentro de Cuadre para ver tu contabilidad."
        error={state.fieldErrors?.["email"]}
      >
        {(control) => (
          <Input
            {...control}
            name="email"
            type="email"
            inputMode="email"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={320}
            defaultValue={state.values?.["email"] ?? ""}
          />
        )}
      </FormRow>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Invitando…" : "Invitar"}
        </Button>
        <Feedback state={state.status === "error" ? { status: "idle" } : state} />
      </div>
    </form>
  );
}
