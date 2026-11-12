import Link from "next/link";

// Dentro del layout de la aplicación. Para el gestor, un autónomo sin vínculo (o revocado, o de otro gestor) es lo mismo que uno que no existe: la API
// contesta igual y esta página no distingue.
export default function OwnerNotFound() {
  return (
    <section aria-labelledby="no-encontrado" className="grid max-w-[70ch] gap-3">
      <h1 id="no-encontrado">No encontramos a ese autónomo</h1>
      <p className="text-ink-soft">Puede que la dirección no sea correcta o que ya no tengas acceso a su contabilidad.</p>
      <p>
        <Link href="/cartera" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Volver a la cartera
        </Link>
      </p>
    </section>
  );
}
