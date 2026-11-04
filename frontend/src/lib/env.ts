// Variables públicas del frontend (T-15: solo NEXT_PUBLIC_*; la clave de servicio no existe para esta aplicación).
// Los accesos son literales para que Next los sustituya en el bundle.

const MISSING = "Falta configurar el frontend: copia frontend/.env.example a frontend/.env.local y rellénalo (ver README).";

export function supabasePublicConfig(): { url: string; key: string } {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error(MISSING);
  return { url, key };
}

export function apiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!url) throw new Error(MISSING);
  return url;
}
