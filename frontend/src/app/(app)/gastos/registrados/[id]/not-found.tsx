import Link from "next/link";

// Dentro del layout de la aplicación: para la persona, un gasto ajeno es lo mismo que uno que no existe.
export default function ExpenseNotFound() {
  return (
    <section aria-labelledby="no-encontrado" className="grid max-w-[70ch] gap-3">
      <h1 id="no-encontrado">No encontramos ese gasto</h1>
      <p className="text-ink-soft">Puede que la dirección no sea correcta.</p>
      <p>
        <Link href="/gastos" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Volver a Gastos
        </Link>
      </p>
    </section>
  );
}
