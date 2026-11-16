import type { Metadata } from "next";
import Link from "next/link";

import { ReportPicker } from "@/components/report/report-picker";
import { ReportView } from "@/components/report/report-view";
import { madridToday } from "@/lib/invoices";
import { chooseMonth, parseMonthlyQuery } from "@/lib/monthly";
import { getMonthlyClosings } from "@/lib/monthly-api";
import { getMonthlyReport } from "@/lib/report-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Reporte mensual" };

export default async function ReportePage(props: PageProps<"/reporte">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  const today = madridToday(new Date());
  // El año y el mes viven en la dirección (`?anio=&mes=`): es una lectura de servidor, sin estado en el navegador.
  const query = parseMonthlyQuery(params, today);
  // La lista del año solo sirve para elegir el mes por defecto (el último cerrado); las cifras del reporte son las de `get_monthly_report`.
  const list = await getMonthlyClosings(query.year);
  const chosen = list.status === "ok" ? chooseMonth(list.data.months, query.month) : null;
  const month = chosen?.month ?? query.month;
  const report = month !== null ? await getMonthlyReport(query.year, month) : null;

  return (
    <>
      <header className="mb-6">
        <h1>Reporte mensual</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          De dónde viene lo que facturas, en qué se va y cómo evoluciona. Todo es orientativo y sale de tu contabilidad mensual: no es una declaración.
        </p>
      </header>
      <div className="grid gap-6">
        <ReportPicker year={query.year} month={month} today={today} />
        {list.status === "problem" ? (
          <div role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 text-status-doubt">
            <p className="font-semibold">{list.message}</p>
            <p className="mt-2">
              <Link href="/reporte" className="font-semibold underline underline-offset-2">
                Ir al año en curso
              </Link>
            </p>
          </div>
        ) : report === null ? (
          <p role="status" className="max-w-3xl rounded-panel border border-rule bg-sheet p-4 text-ink-soft">
            Todavía no hay ningún mes con actividad en {query.year}.{" "}
            <Link href="/reporte" className="font-semibold text-action underline underline-offset-2">
              Ir al año en curso
            </Link>
          </p>
        ) : report.status === "problem" ? (
          <p role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 font-semibold text-status-doubt">
            {report.message}
          </p>
        ) : (
          <ReportView report={report.data} />
        )}
      </div>
    </>
  );
}
