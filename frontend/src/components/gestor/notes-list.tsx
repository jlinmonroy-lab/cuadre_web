import Link from "next/link";

import { formatWhen, noteTarget, type GestorNote } from "@/lib/gestor";

/** Las anotaciones que ha dejado tu gestor: solo se leen (no se editan ni se borran). El texto se pinta como texto, respetando los saltos de línea. */
export function NotesList({ notes }: { notes: GestorNote[] }) {
  if (notes.length === 0) return <p className="text-ink-soft">Tu gestor todavía no ha dejado anotaciones.</p>;
  return (
    <ul className="grid max-w-3xl gap-3">
      {notes.map((note) => {
        const target = noteTarget(note);
        return (
          <li key={note.id} className="grid gap-1.5 rounded-panel border border-rule bg-sheet p-4">
            <p className="whitespace-pre-line [overflow-wrap:anywhere]">{note.body}</p>
            <p className="text-[13px] text-ink-soft">
              <span className="[overflow-wrap:anywhere]">{note.gestor_email ?? "Tu gestor"}</span> ·{" "}
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
