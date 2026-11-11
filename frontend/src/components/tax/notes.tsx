/** Los avisos fijos que manda el servidor (orientativo, lo que no incluye, Canarias, Ceuta y Melilla y, con la casilla 59, el modelo 349). Siempre visibles. */
export function TaxNotes({ notes }: { notes: readonly string[] }) {
  return (
    <section aria-labelledby="avisos-303" className="max-w-3xl">
      <h2 id="avisos-303" className="text-base">
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
