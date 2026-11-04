import type { Metadata } from "next";

import { Portada } from "@/components/portada";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Cartera" };

export default async function CarteraPage() {
  const me = await requireRole("gestor");
  return (
    <Portada
      me={me}
      intro="Esta es tu portada de gestor. Consultas la contabilidad de los autónomos que te dan acceso; no emites ni registras nada por ellos."
      upcoming={[
        { label: "Cartera de autónomos", description: "quienes te han invitado, en modo consulta." },
        { label: "Anotaciones", description: "tus comentarios de revisión, visibles para cada autónomo." },
      ]}
    />
  );
}
