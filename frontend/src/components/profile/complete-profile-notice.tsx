import Link from "next/link";

/** Aviso «Completa tu perfil» (D-11): lo que falta para poder emitir, por nombre, con un enlace a `/perfil`. Texto, no solo color. */
export function CompleteProfileNotice({ missing }: { missing: { field: string; label: string }[] }) {
  return (
    <section aria-labelledby="completa-perfil" className="mb-6 rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 text-status-doubt sm:p-5">
      <h2 id="completa-perfil" className="text-base">
        Completa tu perfil
      </h2>
      <p className="mt-1 text-sm">Para emitir facturas te falta:</p>
      <ul className="mt-1 list-disc pl-5 text-sm font-semibold">
        {missing.map((item) => (
          <li key={item.field}>{item.label}</li>
        ))}
      </ul>
      <p className="mt-3 text-sm">
        <Link href="/perfil" className="font-semibold underline underline-offset-2">
          Ir a mi perfil
        </Link>
      </p>
    </section>
  );
}
