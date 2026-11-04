"use client";

import { useRouter } from "next/navigation";
import { startTransition } from "react";

import { Button } from "@/components/ui/button";

// Se muestra si algo falla al renderizar (la API caída, p. ej.). No se enseña el mensaje del error: puede llevar datos.
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();
  return (
    <main id="main" tabIndex={-1} className="mx-auto grid min-h-dvh w-full max-w-[28rem] content-center gap-4 px-4 py-10">
      <h1>Ahora mismo no podemos cargar esto</h1>
      <p role="alert" className="text-ink-soft">
        El servicio no está disponible. Tu sesión sigue abierta: inténtalo de nuevo en unos minutos.
      </p>
      <div>
        {/* `reset` solo vuelve a pintar en el cliente: hay que pedir de nuevo los componentes de servidor con `refresh`. */}
        <Button
          type="button"
          onClick={() =>
            startTransition(() => {
              router.refresh();
              reset();
            })
          }
        >
          Reintentar
        </Button>
      </div>
    </main>
  );
}
