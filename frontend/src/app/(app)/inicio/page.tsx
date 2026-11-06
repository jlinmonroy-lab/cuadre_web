import type { Metadata } from "next";

import { Portada } from "@/components/portada";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Inicio" };

export default async function InicioPage() {
  const me = await requireRole("usuario");
  return (
    <Portada
      me={me}
      intro="Esta es tu portada de autónomo. Aquí irá el resumen de tu actividad."
      upcoming={[
        { label: "Clientes", description: "tu cartera de clientes con sus datos fiscales." },
        { label: "Facturas", description: "emisión con numeración correlativa y QR de VeriFactu simulado." },
        { label: "Contabilidad mensual", description: "cierre de cada mes y libros de registro." },
        { label: "Trimestres", description: "borradores orientativos de los modelos 303 y 130." },
      ]}
    />
  );
}
