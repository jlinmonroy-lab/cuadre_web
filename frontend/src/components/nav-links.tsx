"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { NavItem } from "@/lib/roles";

// En la barra superior (móvil) los elementos no se parten; en la lateral, sí, para que «Próximamente» no se salga de los 232 px.
const ITEM = "block rounded-md px-3 py-[9px] font-medium whitespace-nowrap nav:whitespace-normal";

/** Navegación del prototipo. Los apartados futuros se muestran desactivados con «Próximamente» (`aria-disabled`, sin foco). */
export function NavLinks({ items, className }: { items: NavItem[]; className?: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Apartados" className={className}>
      <ul className="flex gap-0.5 nav:flex-col">
        {items.map((item) => {
          const current = item.href !== null && (pathname === item.href || pathname.startsWith(`${item.href}/`));
          return (
            <li key={item.label}>
              {item.href !== null ? (
                <Link
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  className={`${ITEM} text-nav-text hover:bg-nav-hover hover:text-sheet aria-[current=page]:bg-nav-current aria-[current=page]:text-sheet aria-[current=page]:shadow-[inset_3px_0_0_var(--color-nav-mark)]`}
                >
                  {item.label}
                </Link>
              ) : (
                <span aria-disabled="true" className={`${ITEM} cursor-not-allowed text-nav-text/60`}>
                  <span className="mr-2">{item.label}</span>
                  <span className="rounded-full bg-nav-hover px-2 py-px align-middle text-[11px] font-semibold text-nav-text">
                    Próximamente
                  </span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
