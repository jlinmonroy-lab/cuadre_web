import { BarList, type Bar } from "@/components/report/bar-list";
import { ChartFigure, DataTable } from "@/components/report/chart-figure";
import { ReportFigures } from "@/components/report/report-figures";
import { SCOPE_BAR, ScopeBar } from "@/components/report/scope-bar";
import { SetAside } from "@/components/report/set-aside";
import { TrendChart } from "@/components/report/trend-chart";
import { SCOPE_LABEL } from "@/lib/invoices";
import { formatCents } from "@/lib/money";
import { monthTitle } from "@/lib/monthly";
import {
  EXPENSES_EMPTY,
  categoriesSummary,
  clientsSummary,
  formatBp,
  scopesSummary,
  trendStatus,
  trendSummary,
  type MonthlyReport,
} from "@/lib/report";

/** El reporte de un mes con todos sus bloques. Los importes, cuotas y variaciones son los del servidor: aquí no se suma ni se compara nada. */
export function ReportView({ report }: { report: MonthlyReport }) {
  const title = `${monthTitle(report.month)} de ${report.year}`;
  const clientBars: Bar[] = report.by_client.map((client) => ({
    key: `${client.client_id}-${client.scope}`,
    label: (
      <>
        {client.name} <span className="text-[13px] text-ink-soft">({SCOPE_LABEL[client.scope]})</span>
      </>
    ),
    cents: client.base_cents,
    tone: SCOPE_BAR[client.scope],
  }));
  const categoryBars: Bar[] = report.expenses_by_category.map((category) => ({ key: category.category, label: category.label, cents: category.expenses_cents, tone: "bg-scope-non-eu" }));

  return (
    <div className="grid gap-6">
      <ReportFigures report={report} />

      <section aria-labelledby="reporte-ingresos" className="grid gap-3">
        <h2 id="reporte-ingresos" className="text-base">
          De dónde viene lo que has facturado
        </h2>
        <p className="max-w-[70ch] text-[13px] text-ink-soft">Bases imponibles, sin IVA. Las rectificativas restan en el mes de su fecha.</p>
        <div className="grid gap-4 min-[900px]:grid-cols-2">
          <ChartFigure
            id="grafico-ambitos"
            title="Por ámbito"
            summary={scopesSummary(report)}
            table={
              <DataTable
                caption={`Ingresos por ámbito en ${title}`}
                head={["Ámbito", "Base imponible", "Cuota"]}
                rows={report.scopes.map((scope) => ({
                  key: scope.scope,
                  cells: [SCOPE_LABEL[scope.scope], formatCents(scope.base_cents), scope.share_bp === null ? "—" : formatBp(scope.share_bp)],
                }))}
              />
            }
          >
            <ScopeBar scopes={report.scopes} />
          </ChartFigure>
          <ChartFigure
            id="grafico-clientes"
            title="Por cliente"
            summary={clientsSummary(report)}
            table={
              <DataTable
                caption={`Ingresos por cliente en ${title}`}
                head={["Cliente", "Ámbito", "Base imponible"]}
                rows={report.by_client.map((client) => ({
                  key: `${client.client_id}-${client.scope}`,
                  cells: [client.name, SCOPE_LABEL[client.scope], formatCents(client.base_cents)],
                }))}
              />
            }
          >
            <BarList bars={clientBars} empty="No hay facturas emitidas este mes." />
          </ChartFigure>
        </div>
      </section>

      <section aria-labelledby="reporte-gastos" className="grid gap-3">
        <h2 id="reporte-gastos" className="text-base">
          En qué se ha gastado
        </h2>
        <p className="max-w-[70ch] text-[13px] text-ink-soft">Base más el IVA que no puedes deducir. El desglose se calcula con los gastos de hoy.</p>
        <ChartFigure
          id="grafico-categorias"
          title="Gastos por categoría"
          summary={categoriesSummary(report)}
          table={
            <DataTable
              caption={`Gastos por categoría en ${title}`}
              head={["Categoría", "Gastos", "Importe"]}
              rows={report.expenses_by_category.map((category) => ({ key: category.category, cells: [category.label, String(category.expense_count), formatCents(category.expenses_cents)] }))}
            />
          }
        >
          <BarList bars={categoryBars} empty={EXPENSES_EMPTY} />
        </ChartFigure>
        {report.expenses_note === null ? null : (
          <p role="status" className="max-w-3xl rounded-panel border border-status-doubt-line bg-status-doubt-bg p-4 text-[15px] text-status-doubt">
            {report.expenses_note}
          </p>
        )}
      </section>

      <section aria-labelledby="reporte-evolucion" className="grid gap-3">
        <h2 id="reporte-evolucion" className="text-base">
          Cómo ha ido en los últimos meses
        </h2>
        <ChartFigure
          id="grafico-evolucion"
          title="Ingresos y gastos por mes"
          summary={trendSummary(report)}
          table={
            <DataTable
              caption="Ingresos y gastos de los últimos meses"
              head={["Mes", "Ingresos", "Gastos"]}
              rows={report.trend.map((point) => ({
                key: `${point.year}-${point.month}`,
                current: point.year === report.year && point.month === report.month,
                cells: [
                  <>
                    {monthTitle(point.month)} de {point.year}
                    <span className="block text-[12px] text-ink-soft">{trendStatus(point)}</span>
                  </>,
                  formatCents(point.total_cents),
                  formatCents(point.expenses_cents),
                ],
              }))}
            />
          }
        >
          <TrendChart trend={report.trend} year={report.year} month={report.month} />
        </ChartFigure>
      </section>

      <SetAside quarter={report.quarter} quarterYear={report.quarter_year} />
    </div>
  );
}
