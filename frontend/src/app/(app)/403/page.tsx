import type { Metadata } from "next";
import Link from "next/link";

import { homeFor } from "@/lib/roles";
import { getMe } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Sin acceso" };

export default async function ForbiddenPage() {
  const me = await getMe();
  return (
    <section aria-labelledby="forbidden-title" className="grid max-w-[70ch] gap-3">
      <h1 id="forbidden-title">No tienes acceso a esta sección</h1>
      <p className="text-ink-soft">Tu cuenta no tiene permiso para ver esta página.</p>
      <p>
        <Link href={homeFor(me.role)} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Volver a mi portada
        </Link>
      </p>
    </section>
  );
}
