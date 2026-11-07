"use client";

import { Ban } from "lucide-react";
import { useEffect, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { voidExpense } from "@/lib/expenses-actions";

/** «Anular gasto» en dos pasos y sin `confirm()` del navegador (que no se puede dar estilo, ni anunciar bien, ni probar). */
export function VoidButton({ expenseId, fromDocument }: { expenseId: string; fromDocument: boolean }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const cancel = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirming) cancel.current?.focus(); // por defecto, la opción segura
  }, [confirming]);

  if (!confirming) {
    return (
      <Button type="button" variant="outline" onClick={() => setConfirming(true)}>
        <Ban aria-hidden="true" />
        Anular gasto
      </Button>
    );
  }

  return (
    <div role="group" aria-labelledby="anular-pregunta" className="grid gap-2 rounded-md border border-status-error bg-status-error-bg px-3 py-2.5">
      <p id="anular-pregunta" className="text-sm font-semibold text-status-error">
        {fromDocument
          ? "¿Anular este gasto? Deja de contar en tus cuentas y el documento vuelve a «Para revisar» para que lo corrijas y lo registres de nuevo."
          : "¿Anular este gasto? Deja de contar en tus cuentas y no se puede recuperar."}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="destructive"
          disabled={pending}
          onClick={() =>
            startTransition(async () => {
              setError(null);
              const result = await voidExpense(expenseId); // si sale bien, redirige y no vuelve
              if (result.status === "error") setError(result.message ?? "No se ha podido anular.");
            })
          }
        >
          {pending ? "Anulando…" : "Sí, anular"}
        </Button>
        <Button ref={cancel} type="button" variant="outline" disabled={pending} onClick={() => setConfirming(false)}>
          Cancelar
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
