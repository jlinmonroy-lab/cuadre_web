import Link from "next/link";
import type { ReactNode } from "react";

import { NavLinks } from "@/components/nav-links";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth-actions";
import { homeFor, navFor, roleLabel } from "@/lib/roles";
import type { Me } from "@/lib/session";

/** Barra lateral desde 901 px; por debajo, barra superior desplazable (como el prototipo). «Cerrar sesión» siempre alcanzable. */
export function AppShell({ me, children }: { me: Me; children: ReactNode }) {
  return (
    <div className="min-h-dvh nav:grid nav:grid-cols-[232px_1fr]">
      <aside
        aria-label="Cuenta y apartados"
        className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 bg-nav px-4 py-3 text-nav-text nav:sticky nav:top-0 nav:flex nav:h-dvh nav:flex-col nav:items-stretch nav:gap-8 nav:py-8"
      >
        <Link
          href={homeFor(me.role)}
          className="col-start-1 row-start-1 px-3 font-head text-[1.625rem] leading-none font-bold text-sheet no-underline nav:px-3"
        >
          Cuadre
        </Link>
        {/* Móvil: marca y «Cerrar sesión» arriba (siempre visibles) y la navegación desplazable debajo. */}
        <NavLinks items={navFor(me.role)} className="col-span-2 row-start-2 -mx-1 overflow-x-auto px-1 py-1 [scrollbar-color:var(--color-nav-current)_transparent] [scrollbar-width:thin] nav:mx-0 nav:overflow-visible nav:p-0" />
        <div className="col-start-2 row-start-1 flex items-center gap-3 nav:mt-auto nav:flex-col nav:items-stretch nav:px-3">
          <p className="hidden text-[13px] nav:block">
            <strong className="block font-semibold text-[#e6ece8]">{me.display_name || me.email}</strong>
            {roleLabel(me.role)}
          </p>
          <form action={logout}>
            <Button
              type="submit"
              variant="outline"
              size="sm"
              className="border-nav-current bg-transparent whitespace-nowrap text-nav-text hover:bg-nav-hover hover:text-sheet nav:w-full"
            >
              Cerrar sesión
            </Button>
          </form>
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="mx-0 w-full max-w-[1240px] min-w-0 px-4 pt-6 pb-12 nav:px-12 nav:pt-8">
        {children}
      </main>
    </div>
  );
}

export function ShellSkeleton() {
  return (
    <div aria-hidden="true" className="min-h-dvh nav:grid nav:grid-cols-[232px_1fr]">
      <div className="h-14 bg-nav nav:h-dvh" />
      <div className="grid content-start gap-4 px-4 pt-6 nav:px-12 nav:pt-8">
        <div className="h-9 w-64 max-w-full rounded bg-muted" />
        <div className="h-32 rounded-panel bg-muted" />
      </div>
    </div>
  );
}
