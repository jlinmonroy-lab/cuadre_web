import Link from "next/link";

import { OWNER_NOTE_LINKS, formatWhen, noteTarget, type GestorNote, type NoteLinks } from "@/lib/gestor";

/**
 * Las anotaciones de un gestor: solo se leen (no se editan ni se borran). El texto se pinta como texto, respetando los saltos de línea. Por defecto, las
 * ve el autónomo; la ficha del gestor pasa sus enlaces, su mensaje de vacío y «Tú» como autor (no recibe su propio correo).
 */
export function NotesList({
  notes,
  links = OWNER_NOTE_LINKS,
  empty = "Tu gestor todavía no ha dejado anotaciones.",
  author = "Tu gestor",
}: {
  notes: GestorNote[];
  links?: NoteLinks;
  empty?: string;
  author?: string;
}) {
  if (notes.length === 0) return <p className="text-ink-soft">{empty}</p>;
  return (
    <ul className="grid max-w-3xl gap-3">
      {notes.map((note) => {
        const target = noteTarget(note, links);
        return (
          <li key={note.id} className="grid gap-1.5 rounded-panel border border-rule bg-sheet p-4">
            <p className="whitespace-pre-line [overflow-wrap:anywhere]">{note.body}</p>
            <p className="text-[13px] text-ink-soft">
              <span className="[overflow-wrap:anywhere]">{note.gestor_email ?? author}</span> ·{" "}
              <time dateTime={note.created_at}>{formatWhen(note.created_at)}</time>
            </p>
            {target ? (
              <p className="text-[13px]">
                {target.href ? (
                  <Link href={target.href} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                    {target.label}
                  </Link>
                ) : (
                  <span className="text-ink-soft">{target.label}</span>
                )}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
