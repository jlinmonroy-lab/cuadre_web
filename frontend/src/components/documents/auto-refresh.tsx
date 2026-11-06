"use client";

import { useRouter } from "next/navigation";
import { startTransition, useEffect } from "react";

/**
 * Vuelve a pedir la página cada 2 s mientras `active` (hay algo leyéndose) y la pestaña está a la vista. Cubre las recargas de la
 * página y las lecturas que lanzó otra pestaña u otro dispositivo; se apaga solo, porque la API presenta como fallida una lectura
 * de más de 120 s sin cambios (AC-11), así que `active` acaba siendo falso.
 */
export function AutoRefresh({ active, intervalMs = 2000 }: { active: boolean; intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") startTransition(() => router.refresh());
    }, intervalMs);
    return () => clearInterval(timer);
  }, [active, intervalMs, router]);
  return null;
}
