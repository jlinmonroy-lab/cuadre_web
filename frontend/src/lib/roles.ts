// Roles, portadas y navegación (SPEC-W-001 §5.3). Los identificadores de rol van en español (CLAUDE.md).
// El rol NUNCA sale del JWT: lo devuelve GET /api/me. Sin dependencias ni alias: lo ejecutan directamente los tests.

export const ROLES = ["usuario", "gestor", "admin"] as const;
export type Role = (typeof ROLES)[number];

export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

const HOME: Record<Role, string> = { usuario: "/inicio", gestor: "/cartera", admin: "/admin" };
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
        FUTURE("Clientes"),
        FUTURE("Facturas"),
        FUTURE("Gastos"),
        FUTURE("Contabilidad mensual"),
        FUTURE("Trimestres"),
      ];
    case "gestor":
      return [{ label: "Cartera", href: HOME.gestor }];
    case "admin":
      return [FUTURE("Cuentas")];
  }
}

/** Rol al que pertenece una ruta de portada (y sus subrutas), respetando el límite de segmento: «/administracion» no es «/admin». */
export function portadaOwner(pathname: string): Role | null {
  for (const role of ROLES) {
    const home = HOME[role];
    if (pathname === home || pathname.startsWith(`${home}/`)) return role;
  }
  return null;
}
