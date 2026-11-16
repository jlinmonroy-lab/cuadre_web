import type { Metadata } from "next";

import { Portada } from "@/components/portada";
import { CompleteProfileNotice } from "@/components/profile/complete-profile-notice";
import { getProfileForNotice } from "@/lib/profile-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Inicio" };

export default async function InicioPage() {
  const me = await requireRole("usuario");
  // SPEC-W-005 D-11: mientras falte algo para emitir, la portada lo dice por nombre. Si el perfil no se puede leer, se omite el aviso.
  const profile = await getProfileForNotice();
  return (
    <>
      {profile && !profile.completeness.can_issue ? <CompleteProfileNotice missing={profile.completeness.missing_for_invoicing} /> : null}
      <Portada
        me={me}
        intro="Esta es tu portada de autónomo. Aquí irá el resumen de tu actividad."
        upcoming={[]}
      />
    </>
  );
}
