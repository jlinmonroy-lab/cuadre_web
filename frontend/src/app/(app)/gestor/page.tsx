import type { Metadata } from "next";

import { AccessList } from "@/components/gestor/access-list";
import { ActivityList } from "@/components/gestor/activity-list";
import { InviteForm } from "@/components/gestor/invite-form";
import { NotesList } from "@/components/gestor/notes-list";
import { parseCursor } from "@/lib/gestor";
import { listAccesses, listActivity, listNotes } from "@/lib/gestor-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Mi gestor" };

export default async function GestorPage(props: PageProps<"/gestor">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  // El cursor del registro viene de la dirección (entrada no confiable): solo un entero; con otra cosa se enseña la primera página.
  const cursor = parseCursor(params["actividad"]);
  const [accesses, notes, activity] = await Promise.all([listAccesses(), listNotes(), listActivity(cursor)]);

  return (
    <>
      <header className="mb-6">
        <h1>Mi gestor</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          Invita a tu gestor para que consulte tu contabilidad. Solo puede leerla y dejarte anotaciones: no emite, registra ni cambia nada por ti. Puedes
          retirarle el acceso cuando quieras y aquí ves todo lo que ha consultado.
        </p>
      </header>
      <div className="grid gap-8">
        <section aria-labelledby="invitar" className="grid gap-3">
          <h2 id="invitar" className="text-lg">
            Invitar a tu gestor
          </h2>
          <InviteForm />
        </section>
        <section aria-labelledby="accesos" className="grid gap-3">
          <h2 id="accesos" className="text-lg">
            Accesos
          </h2>
          <AccessList accesses={accesses} />
        </section>
        <section aria-labelledby="anotaciones" className="grid gap-3">
          <h2 id="anotaciones" className="text-lg">
            Anotaciones de tu gestor
          </h2>
          <NotesList notes={notes} />
        </section>
        <section aria-labelledby="actividad" className="grid gap-3">
          <h2 id="actividad" className="text-lg">
            Qué ha consultado tu gestor
          </h2>
          <ActivityList items={activity.items} accesses={accesses} nextCursor={activity.next_cursor} isFirstPage={cursor === undefined} />
        </section>
      </div>
    </>
  );
}
