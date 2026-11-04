import type { Metadata } from "next";

import { Portada } from "@/components/portada";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Administración" };

export default async function AdminPage() {
  const me = await requireRole("admin");
  return (
    <Portada
      me={me}
      intro="Esta es la portada de administración. Gestionas cuentas y contenidos de la plataforma; no tienes acceso a los datos financieros de nadie."
      upcoming={[
        { label: "Cuentas", description: "alta y promoción de gestores, y suspensión de cuentas." },
        { label: "Base de conocimiento", description: "los contenidos que consulta el asistente." },
      ]}
    />
  );
}
