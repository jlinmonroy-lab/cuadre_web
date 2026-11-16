// Los datos de `reporte.spec.ts` (SPEC-W-013 hito 5): dos meses terminados con facturas a los tres ámbitos y gastos de varias categorías, cerrados con la CLI del job
// (solo para la cuenta de la prueba), y lo que dice la API de ellos (el ORÁCULO: la cuenta del worker acumula documentos que no se pueden borrar, RES-03, así que
// ninguna prueba espera cifras absolutas).
import { randomUUID } from "node:crypto";

import type { TestInfo } from "@playwright/test";

import type { Biller } from "./fixtures";
import { madridToday } from "./invoices";
import type { Ledger } from "./ledger";
import { MonthlyApi, monthKey, previousMonth, type MonthlyReport } from "./monthly";

export type ReportMonths = {
  /** El mes anterior al de hoy (el reporte que se prueba) y el anterior a ese. */
  year: number;
  month: number;
  before: { year: number; month: number };
  concept: string;
  report: MonthlyReport;
};

/**
 * El mes anterior (P) con una factura a cada ámbito y tres gastos de categorías distintas, y el anterior a ese (Q) con una factura y un gasto; cierra los dos y
 * devuelve el reporte de P según la API. Una serie nueva por prueba: así admite facturas con fecha pasada, emitidas en orden (Q antes que P).
 */
export async function prepareReportMonths(biller: Biller, ledger: Ledger, monthly: MonthlyApi, testInfo: TestInfo): Promise<ReportMonths> {
  const { year, month } = previousMonth(madridToday());
  const before = previousMonth(`${year}-${String(month).padStart(2, "0")}-15`);
  const concept = `E2E ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;
  const series = await biller.invoices.createSeries(`R${randomUUID().slice(0, 6).toUpperCase()}`);
  const issue = (clientId: string, base: number, key: string, day: string) =>
    biller.invoices.issue({ client_id: clientId, concept, base_cents: base, issue_date: `${key}-${day}`, series_id: series.id });

  const q = monthKey(before.year, before.month);
  await issue(biller.clients.national.id, 100_000, q, "05");
  await ledger.create(`Gasto Q ${concept}`, `${q}-10`, 2_000, "software");

  const p = monthKey(year, month);
  await issue(biller.clients.national.id, 120_000, p, "03");
  await issue(biller.clients.euBusiness.id, 30_000, p, "10");
  await issue(biller.clients.mxBusiness.id, 25_000, p, "17");
  await ledger.create(`Software ${concept}`, `${p}-05`, 5_000, "software");
  await ledger.create(`Asesoría ${concept}`, `${p}-06`, 20_000, "advisory");
  await ledger.create(`Otros ${concept}`, `${p}-07`, 3_000, "other");

  await monthly.close(before.year, before.month);
  await monthly.close(year, month);
  return { year, month, before, concept, report: await monthly.report(year, month) };
}
