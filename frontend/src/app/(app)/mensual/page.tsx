import type { Metadata } from "next";
import Link from "next/link";

import { MonthDetail } from "@/components/monthly/month-detail";
import { MonthsTable } from "@/components/monthly/months-table";
import { YearPicker } from "@/components/monthly/year-picker";
import { madridToday } from "@/lib/invoices";
import { COVERAGE_NOTE, chooseMonth, parseMonthlyQuery } from "@/lib/monthly";
import { getMonthlyClosing, getMonthlyClosings } from "@/lib/monthly-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Contabilidad mensual" };

export default async function MensualPage(props: PageProps<"/mensual">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  const today = madridToday(new Date());
  // El año y el mes viven en la dirección (`?anio=&mes=`): es una lectura de servidor, sin estado en el navegador.
  const query = parseMonthlyQuery(params, today);
  const list = await getMonthlyClosings(query.year);
  const chosen = list.status === "ok" ? chooseMonth(list.data.months, query.month) : null;
  const detail = chosen !== null ? await getMonthlyClosing(query.year, chosen.month) : null;

  return (
    <>
      <header className="mb-6">
        <h1>Contabilidad mensual</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          Cada mes se cierra solo el día 1 del siguiente. Los importes de ingresos son bases imponibles, sin IVA. Aquí ves de dónde viene lo que facturas y cuánto llevas en el
          año.
        </p>
      </header>
      <div className="grid gap-6">
        <YearPicker year={query.year} today={today} />
        {list.status === "ok" ? (
          <>
            <section aria-labelledby="meses-del-anio" className="grid gap-3">
              <h2 id="meses-del-anio" className="text-base">
                Meses de {list.data.year}
              </h2>
              <MonthsTable data={list.data} selected={chosen?.month ?? null} />
              <p className="max-w-[70ch] text-[13px] text-ink-soft">{COVERAGE_NOTE}</p>
            </section>
            {detail?.status === "ok" ? <MonthDetail detail={detail.data} /> : null}
            {detail?.status === "problem" ? (
              <p role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 font-semibold text-status-doubt">
                {detail.message}
              </p>
            ) : null}
          </>
        ) : (
          <div role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 text-status-doubt">
            <p className="font-semibold">{list.message}</p>
            <p className="mt-2">
              <Link href="/mensual" className="font-semibold underline underline-offset-2">
                Ir al año en curso
              </Link>
            </p>
          </div>
        )}
      </div>
    </>
  );
}
