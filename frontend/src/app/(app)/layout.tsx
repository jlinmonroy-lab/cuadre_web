import type { ReactNode } from "react";
import { Suspense } from "react";

import { AppShell, ShellSkeleton } from "@/components/app-shell";
import { getMe } from "@/lib/session";

// Cada apartado depende de la sesión y de GET /api/me en cada navegación: no puede ser «instantáneo» en el sentido de Cache Components
// (no hay nada que cachear entre personas). Se declara para que la validación de desarrollo no lo señale como un fallo.
export const instant = false;

// Con Cache Components, leer la sesión (cookies) es un dato de la petición: va dentro de Suspense y no en lo alto del layout.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<ShellSkeleton />}>
      <AuthenticatedShell>{children}</AuthenticatedShell>
    </Suspense>
  );
}

async function AuthenticatedShell({ children }: { children: ReactNode }) {
  const me = await getMe(); // 401/403 → cierra la sesión con aviso; API caída → app/error.tsx
  return <AppShell me={me}>{children}</AppShell>;
}
