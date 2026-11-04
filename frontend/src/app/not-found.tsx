import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" tabIndex={-1} className="mx-auto grid min-h-dvh w-full max-w-[28rem] content-center gap-4 px-4 py-10">
      <h1>No encontramos esa página</h1>
      <p className="text-ink-soft">Puede que la dirección esté mal escrita o que la página ya no exista.</p>
      <p>
        <Link href="/" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Ir al inicio
        </Link>
      </p>
    </main>
  );
}
