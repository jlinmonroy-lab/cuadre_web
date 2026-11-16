import { roleLabel } from "@/lib/roles";
import type { Me } from "@/lib/session";

export type Upcoming = { label: string; description: string };

/** Portada mínima de un rol (SPEC-W-001 §3.4): nombre, rol y las secciones que llegarán, desactivadas (sin ninguna, no hay sección). */
export function Portada({ me, intro, upcoming }: { me: Me; intro: string; upcoming: Upcoming[] }) {
  const firstName = me.display_name.trim().split(/\s+/)[0] ?? "";
  return (
    <>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>Hola, {firstName || me.email}</h1>
          <p className="mt-1 max-w-[70ch] text-ink-soft">{intro}</p>
        </div>
        <span className="rounded-full bg-action-soft px-2.5 py-0.5 text-[13px] font-semibold whitespace-nowrap text-action-hover">
          {roleLabel(me.role)}
        </span>
      </header>
      {upcoming.length === 0 ? null : (
        <section aria-labelledby="proximamente" className="rounded-panel border border-rule bg-sheet p-6">
          <h2 id="proximamente" className="mb-3">
            Próximamente
          </h2>
          <ul className="grid gap-3">
            {upcoming.map((item) => (
              <li key={item.label}>
                <strong className="font-semibold">{item.label}</strong>
                <span className="text-ink-soft"> · {item.description}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
