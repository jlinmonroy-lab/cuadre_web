// Roles, portadas y navegación (SPEC-W-001 §5.3). Los identificadores de rol van en español (CLAUDE.md).
// El rol NUNCA sale del JWT: lo devuelve GET /api/me. Sin dependencias ni alias: lo ejecutan directamente los tests.

export const ROLES = ["usuario", "gestor", "admin"] as const;
export type Role = (typeof ROLES)[number];

export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

const HOME: Record<Role, string> = { usuario: "/inicio", gestor: "/cartera", admin: "/admin" };
// Apartados con pantalla propia, además de la portada: pertenecen a un solo rol y exigen sesión (SPEC-W-002: Gastos; SPEC-W-005: Perfil;
// SPEC-W-006: Clientes).
const SECTIONS: Record<Role, readonly string[]> = { usuario: ["/gastos", "/perfil", "/clientes"], gestor: [], admin: [] };
const LABEL: Record<Role, string> = { usuario: "Autónomo", gestor: "Gestor", admin: "Administrador" };

export function homeFor(role: Role): string {
  return HOME[role];
}

export function roleLabel(role: Role): string {
  return LABEL[role];
}

/** `href: null` = apartado futuro: se muestra desactivado con «Próximamente». */
export type NavItem = { label: string; href: string | null };

const FUTURE = (label: string): NavItem => ({ label, href: null });

export function navFor(role: Role): NavItem[] {
  switch (role) {
    case "usuario":
      return [
        { label: "Inicio", href: HOME.usuario },
        { label: "Clientes", href: "/clientes" },
        FUTURE("Facturas"),
        { label: "Gastos", href: "/gastos" },
        FUTURE("Contabilidad mensual"),
        FUTURE("Trimestres"),
        { label: "Perfil", href: "/perfil" },
      ];
    case "gestor":
      return [{ label: "Cartera", href: HOME.gestor }];
    case "admin":
      return [FUTURE("Cuentas")];
  }
}

const within = (pathname: string, base: string) => pathname === base || pathname.startsWith(`${base}/`);

/** Rol al que pertenece una ruta de portada (y sus subrutas), respetando el límite de segmento: «/administracion» no es «/admin». */
export function portadaOwner(pathname: string): Role | null {
  for (const role of ROLES) if (within(pathname, HOME[role])) return role;
  return null;
}

/** Rol al que pertenece una portada o un apartado (`/gastos`…), con el mismo límite de segmento. Lo usa el proxy para exigir sesión. */
export function sectionOwner(pathname: string): Role | null {
  const home = portadaOwner(pathname);
  if (home !== null) return home;
  for (const role of ROLES) if (SECTIONS[role].some((section) => within(pathname, section))) return role;
  return null;
}
