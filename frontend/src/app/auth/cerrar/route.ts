// Cierre de sesión forzado: lo usa `getMe()` cuando la API rechaza la sesión (token inválido, cuenta suspendida, perfil ausente).
// No se pueden borrar cookies al renderizar un Server Component, de ahí esta ruta. El cierre voluntario es la acción `logout`.
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { noticeFor } from "@/lib/notices";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  // Una petición GET entre sitios (una imagen en otra web, p. ej.) no debe poder cerrar la sesión de nadie.
  const origin = request.headers.get("sec-fetch-site");
  if (origin !== null && origin !== "same-origin" && origin !== "none") redirect("/login");

  const requested = request.nextUrl.searchParams.get("aviso");
  const notice = noticeFor(requested) ? requested : "sesion";

  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut({ scope: "local" });
  redirect(`/login?aviso=${notice}`);
}
