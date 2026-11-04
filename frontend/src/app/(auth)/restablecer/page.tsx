import type { Metadata } from "next";

import { AuthCard } from "@/components/auth/auth-card";
import { ResetForm } from "@/components/auth/forms";

export const metadata: Metadata = { title: "Nueva contraseña" };

// El proxy solo deja pasar aquí a quien llega con la sesión que crea el enlace de recuperación (/auth/confirm);
// la acción vuelve a comprobarlo.
export default function ResetPage() {
  return (
    <AuthCard title="Elige una contraseña nueva">
      <ResetForm />
    </AuthCard>
  );
}
