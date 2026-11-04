// Destino de los enlaces de los correos de Supabase Auth (confirmación de cuenta y recuperación de contraseña).
// Sin interfaz: canjea el `token_hash` y redirige. Plantillas en supabase/templates/.
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { safeNext } from "@/lib/safe-next";
import { createSupabaseServerClient } from "@/lib/supabase/server";

// Solo los tipos que usamos; cualquier otro (invite, magiclink, email_change…) se rechaza.
const TYPES = ["email", "recovery"] as const;
type ConfirmType = (typeof TYPES)[number];
const isConfirmType = (value: string | null): value is ConfirmType => TYPES.some((type) => type === value);

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const tokenHash = params.get("token_hash");
  const type = params.get("type");

  if (tokenHash && isConfirmType(type)) {
    const supabase = await createSupabaseServerClient();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash: tokenHash });
    if (!error) redirect(safeNext(params.get("next"), "/")); // `/` lleva a la portada del rol
  }
  redirect("/login?aviso=enlace");
}
