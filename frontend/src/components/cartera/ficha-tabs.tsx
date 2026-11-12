import Link from "next/link";

import { TABS, TAB_LABEL, fichaHref, type Tab } from "@/lib/gestor-cartera";

/**
 * Las pestañas de la ficha. Son enlaces (no `role="tab"`): la pestaña vive en la dirección, se recorren con el teclado como cualquier enlace y funcionan sin
 * JavaScript. La elegida lleva `aria-current` y se distingue también por la forma (fondo oscuro), no solo por el color. En móvil se parten en varias líneas.
 */
export function FichaTabs({ ownerId, current }: { ownerId: string; current: Tab }) {
  return (
    <nav aria-label="Secciones de la ficha">
      <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {TABS.map((tab) => (
          <li key={tab}>
            <Link
              href={fichaHref(ownerId, tab)}
              aria-current={tab === current ? "page" : undefined}
              className={`inline-block rounded-lg border px-3.5 py-2 font-semibold ${
                tab === current ? "border-ink bg-ink text-sheet" : "border-rule-strong bg-sheet text-ink hover:bg-paper"
              }`}
            >
              {TAB_LABEL[tab]}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
