import Link from "next/link";

// Dentro del layout de la aplicación: para la persona, una factura ajena es lo mismo que una que no existe.
export default function InvoiceNotFound() {
  return (
    <section aria-labelledby="no-encontrada" className="grid max-w-[70ch] gap-3">
      <h1 id="no-encontrada">No encontramos esa factura</h1>
      <p className="text-ink-soft">Puede que la dirección no sea correcta o que la factura no sea tuya.</p>
      <p>
        <Link href="/facturas" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Volver a Facturas
        </Link>
      </p>
    </section>
  );
}
