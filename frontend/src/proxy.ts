// Next.js 16 llama «proxy» a lo que antes era «middleware». Refresca la sesión de Supabase en cada navegación y aplica las
// redirecciones de `routeGuard`. Solo mejora la experiencia: las Server Functions NO pasan por el matcher, así que cada layout y
// cada acción comprueba lo suyo; la autorización real está en la API (JWT + rol de la base de datos) y en la RLS.
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { supabasePublicConfig } from "@/lib/env";
import { routeGuard } from "@/lib/route-guard";

export async function proxy(request: NextRequest) {
  const { url, key } = supabasePublicConfig();

  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet, headers) {
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) response.cookies.set(name, value, options);
        // Las respuestas que fijan cookies de sesión no deben cachearse en ningún intermediario.
        for (const [header, value] of Object.entries(headers)) response.headers.set(header, value);
      },
    },
  });

  // `getClaims` verifica la firma del JWT contra el JWKS (no se fía de la cookie) y refresca la sesión si hace falta.
  const { data } = await supabase.auth.getClaims();
  const authenticated = Boolean(data?.claims?.sub);

  const decision = routeGuard({
    pathname: request.nextUrl.pathname,
    search: request.nextUrl.search,
    authenticated,
  });
  if (!decision) return response;

  const redirect = NextResponse.redirect(new URL(decision.redirect, request.url));
  // La redirección conserva las cookies refrescadas y las cabeceras de no-cache de la respuesta original.
  for (const cookie of response.cookies.getAll()) redirect.cookies.set(cookie);
  for (const header of ["cache-control", "expires", "pragma"]) {
    const value = response.headers.get(header);
    if (value) redirect.headers.set(header, value);
  }
  return redirect;
}

export const config = {
  // Todo menos los recursos estáticos de Next y las imágenes.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
