// Reglas del proxy (src/proxy.ts). Solo mejoran la experiencia: la autorización real está en la API y en la RLS, y las Server
// Functions no pasan por el matcher del proxy, así que cada layout y cada acción comprueba lo suyo.
// Sin alias: lo ejecutan directamente los tests.
import { sectionOwner } from "./roles.ts";

export type GuardInput = { pathname: string; search: string; authenticated: boolean };
export type GuardResult = { redirect: string } | null;

const FORBIDDEN_PAGE = "/403";
const ANONYMOUS_ONLY = ["/login", "/registro", "/recuperar"];
const NEEDS_RECOVERY_SESSION = ["/restablecer"];

const matches = (pathname: string, base: string) => pathname === base || pathname.startsWith(`${base}/`);

const isProtected = (pathname: string) => sectionOwner(pathname) !== null || matches(pathname, FORBIDDEN_PAGE);

// Las barras se dejan sin codificar para que AC-04 sea literal: /login?next=/inicio.
const encodeNext = (value: string) => encodeURIComponent(value).replaceAll("%2F", "/");

export function routeGuard({ pathname, search, authenticated }: GuardInput): GuardResult {
  if (!authenticated) {
    if (isProtected(pathname)) return { redirect: `/login?next=${encodeNext(pathname + search)}` };
    if (NEEDS_RECOVERY_SESSION.some((base) => matches(pathname, base))) return { redirect: "/recuperar?aviso=enlace" };
    return null;
  }
  // Con sesión, las pantallas de acceso devuelven a la raíz, que lleva a la portada del rol.
  if (ANONYMOUS_ONLY.some((base) => matches(pathname, base))) return { redirect: "/" };
  return null;
}
