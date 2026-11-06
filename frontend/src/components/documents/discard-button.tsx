"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { discardDocument } from "@/lib/documents-actions";

/** «Descartar» en dos pasos y sin `confirm()` del navegador (que no se puede dar estilo, ni anunciar bien, ni probar). Borra el archivo. */
export function DiscardButton({ documentId }: { documentId: string }) {
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
        <Trash2 aria-hidden="true" />
        Descartar
      </Button>
    );
  }

  return (
    <div role="group" aria-labelledby="descartar-pregunta" className="grid gap-2 rounded-md border border-status-error bg-status-error-bg px-3 py-2.5">
      <p id="descartar-pregunta" className="text-sm font-semibold text-status-error">
        ¿Descartar este documento? Se borra el archivo y no se puede deshacer.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="destructive"
          disabled={pending}
          onClick={() =>
            startTransition(async () => {
              setError(null);
              const result = await discardDocument(documentId); // si sale bien, redirige a la lista y no vuelve
              if (result.status === "error") setError(result.message ?? "No se ha podido descartar.");
            })
          }
        >
          {pending ? "Descartando…" : "Sí, descartar"}
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
