// Sesión y cliente de la API para el código que corre en el SERVIDOR de Next (Server Components, Server Actions, Route Handlers).
// El navegador nunca recibe el JWT: se lee de las cookies de sesión y se reenvía a la API, que lo vuelve a verificar.
import "server-only";

import { createApiClient, type ApiClient } from "@/api/client";
import { apiBaseUrl } from "@/lib/env";
import { createSupabaseServerClient } from "@/lib/supabase/server";

/** Token de acceso de una sesión cuya firma se ha verificado, o `null` si no hay sesión. */
export async function sessionToken(): Promise<string | null> {
  const supabase = await createSupabaseServerClient();
  const { data: claims } = await supabase.auth.getClaims();
  if (!claims?.claims?.sub) return null;
  // Aquí `getSession` solo se usa para reenviar el token a la API (que lo vuelve a verificar), nunca para autorizar.
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export function apiFor(token: string): ApiClient {
  return createApiClient(apiBaseUrl(), () => token);
}
