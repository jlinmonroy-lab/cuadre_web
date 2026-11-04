// Cliente de Supabase para Server Components, Server Actions y Route Handlers. Solo se usa para la SESIÓN (cookies); los datos van
// por la API de cuadre-web. Clave publicable únicamente: la clave de servicio no existe para el frontend (T-15).
import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { supabasePublicConfig } from "@/lib/env";

export async function createSupabaseServerClient() {
  const { url, key } = supabasePublicConfig();
  const cookieStore = await cookies();

  return createServerClient(url, key, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) cookieStore.set(name, value, options);
        } catch {
          // Al renderizar un Server Component no se pueden escribir cookies. No importa: el proxy (src/proxy.ts) refresca la
          // sesión en cada navegación antes de que se renderice nada.
        }
      },
    },
  });
}
