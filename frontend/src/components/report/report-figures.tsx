import { MonthStatusBadge } from "@/components/monthly/month-status";
import { formatCents } from "@/lib/money";
import { monthTitle } from "@/lib/monthly";
import { NO_PREVIOUS_MONTH, deltaText, variationText, type MonthlyReport } from "@/lib/report";

function Figure({ label, value, comparison }: { label: string; value: number; comparison: string }) {
  return (
    <div className="grid content-start gap-1 rounded-panel border border-rule bg-sheet p-4">
      <dt className="text-[13px] font-semibold text-ink-soft">{label}</dt>
      <dd className="m-0 text-[22px] font-bold tabular-nums">{formatCents(value)}</dd>
      <dd className="m-0 text-[13px] text-ink-soft">{comparison}</dd>
    </div>
  );
}

/**
 * Las tres cifras del mes: ingresos (bases imponibles, sin IVA), gastos y rendimiento. Cada una con lo que cambió frente al mes anterior, escrito con signo y
 * con palabras. Todos los importes y variaciones son los del servidor.
 */
export function ReportFigures({ report }: { report: MonthlyReport }) {
  const { comparison } = report;
  return (
    <section aria-labelledby="reporte-cifras" className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 id="reporte-cifras" className="text-base">
          {monthTitle(report.month)} de {report.year}
        </h2>
        <MonthStatusBadge status={report.status} />
      </div>
      <dl className="m-0 grid gap-3 min-[720px]:grid-cols-3">
        <Figure label="Ingresos" value={report.total_cents} comparison={comparison ? variationText(comparison.total_variation_bp, comparison.previous_month) : NO_PREVIOUS_MONTH} />
        <Figure label="Gastos" value={report.expenses_cents} comparison={comparison ? variationText(comparison.expenses_variation_bp, comparison.previous_month) : NO_PREVIOUS_MONTH} />
        <Figure label="Rendimiento del mes" value={report.result_cents} comparison={comparison ? deltaText(comparison.result_delta_cents, comparison.previous_month) : NO_PREVIOUS_MONTH} />
      </dl>
    </section>
  );
}
