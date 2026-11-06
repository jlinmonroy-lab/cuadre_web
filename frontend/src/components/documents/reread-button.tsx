"use client";

import { LoaderCircle, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

import { Button } from "@/components/ui/button";
import { readViaHandler } from "@/lib/upload-flow";

/** «Volver a leer»: relanza la lectura del mismo documento (idempotente) y espera hasta 45 s sin bloquear el resto de la pantalla. */
export function RereadButton({ documentId }: { documentId: string }) {
  const router = useRouter();
  const [reading, setReading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function reread() {
    setReading(true);
    setMessage(null);
    const result = await readViaHandler((input, init) => fetch(input, init), documentId, "reread");
    setReading(false);
    if (!result.ok) setMessage(result.message);
    startTransition(() => router.refresh()); // muestra el resultado (o «Leyendo…» si la lectura sigue en curso)
  }

  return (
    <div className="grid gap-1.5">
      <Button type="button" variant="outline" disabled={reading} onClick={() => void reread()}>
        {reading ? <LoaderCircle aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : <RotateCcw aria-hidden="true" />}
        {reading ? "Leyendo…" : "Volver a leer"}
      </Button>
      <div aria-live="polite">
        {message ? <p className="max-w-[40ch] text-sm font-semibold text-status-error">{message}</p> : null}
      </div>
    </div>
  );
}
