import type { Metadata } from "next";
import Link from "next/link";

import { DeadlineStatus } from "@/components/tax/deadline-status";
import { Modelo303Sheet } from "@/components/tax/modelo-303";
import { TaxNotes } from "@/components/tax/notes";
import { QuarterPicker } from "@/components/tax/quarter-picker";
import { madridToday } from "@/lib/invoices";
import { requireRole } from "@/lib/session";
import { getModelo303 } from "@/lib/tax-api";
import { parseQuarterQuery, quarterHref, quarterMonths, quarterOfDate, quarterTitle } from "@/lib/tax";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Trimestres" };

export default async function TrimestresPage(props: PageProps<"/trimestres">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  const today = madridToday(new Date());
  // El trimestre vive en la dirección (`?year=&quarter=`): es una lectura de servidor, sin estado en el navegador.
  const query = parseQuarterQuery(params, today);
  const reading = await getModelo303(query);
  const current = quarterOfDate(today);

  return (
    <>
      <header className="mb-6">
        <h1>Trimestres</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          Borradores orientativos de tus impuestos, calculados con lo que tienes registrado. Cada casilla enseña las facturas y los gastos que la componen. Nada se
          presenta ante la AEAT desde aquí.
        </p>
      </header>
      <div className="grid gap-6">
        <QuarterPicker year={query.year} quarter={query.quarter} today={today} />
        <section aria-labelledby="trimestre-elegido" className="grid gap-3">
          <h2 id="trimestre-elegido" className="text-base">
            {quarterTitle(query.year, query.quarter)}: {quarterMonths(query.quarter)}
          </h2>
          {reading.status === "ok" ? (
            <>
              <DeadlineStatus model={reading.model} />
              <Modelo303Sheet model={reading.model} />
              <TaxNotes notes={reading.model.notes} />
            </>
          ) : (
            <div role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 text-status-doubt">
              <p className="font-semibold">{reading.message}</p>
              <p className="mt-2">
                <Link href={quarterHref(current.year, current.quarter)} className="font-semibold underline underline-offset-2">
                  Ir al trimestre actual
                </Link>
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
