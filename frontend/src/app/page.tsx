import { redirect } from "next/navigation";
import { Suspense } from "react";

import { homeFor } from "@/lib/roles";
import { getMe } from "@/lib/session";

// «/»: lleva a la portada del rol, o a /login si no hay sesión (getMe redirige). Si la API está caída muestra app/error.tsx:
// NUNCA redirige a /login con sesión, porque el proxy la devolvería aquí y se formaría un bucle.
export default function Home() {
  return (
    <Suspense fallback={<main id="main" tabIndex={-1} className="grid min-h-dvh place-items-center text-ink-soft">Cargando…</main>}>
      <RoleRedirect />
    </Suspense>
  );
}

async function RoleRedirect() {
  const me = await getMe();
  return redirect(homeFor(me.role));
}
