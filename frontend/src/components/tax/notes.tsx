import type { ModelKey } from "@/lib/tax";

/**
 * Los avisos fijos que manda el servidor, siempre visibles. En el 303: orientativo, lo que no incluye, Canarias, Ceuta y Melilla y, con la casilla 59, el
 * modelo 349. En el 130: orientativo y acumulado, lo que no incluye y la regla del 70 %.
 */
export function TaxNotes({ notes, model = "303" }: { notes: readonly string[]; model?: ModelKey }) {
  const id = `avisos-${model}`;
  return (
    <section aria-labelledby={id} className="max-w-3xl">
      <h2 id={id} className="text-base">
        Avisos
      </h2>
      <ul className="mt-2 grid list-disc gap-1.5 pl-5 text-[14px] text-ink-soft">
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </section>
  );
}
