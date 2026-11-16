// El reporte mensual en la interfaz (SPEC-W-013 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz DIBUJA lo que dice el servidor y no calcula ningún importe: ni un total, ni una diferencia, ni una cuota, ni un resultado. Aquí solo se leen la
// dirección, se escriben los puntos básicos del servidor como porcentaje (con enteros), se escalan las barras (geometría, no dinero) y se redactan los textos.
import type { components } from "@/api/schema";

import { SCOPE_LABEL } from "./invoices.ts";
import { formatCents } from "./money.ts";
import { MONTH_NAMES, monthName, monthTitle, statusLabel } from "./monthly.ts";
import { quarterHref, type Quarter } from "./tax.ts";

export type MonthlyReport = components["schemas"]["MonthlyReport"];
export type Comparison = components["schemas"]["ComparisonOut"];
export type ScopeShare = components["schemas"]["ScopeShareOut"];
export type CategoryTotal = components["schemas"]["CategoryTotalOut"];
export type TrendPoint = components["schemas"]["TrendPoint"];

export const reportHref = (year: number, month: number): string => `/reporte?anio=${year}&mes=${month}`;

/** El nombre corto de un mes para una columna de la tendencia: `sep.` */
const SHORT = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sept.", "oct.", "nov.", "dic."] as const;
export const shortMonth = (month: number): string => SHORT[month - 1] ?? "";

/** Los doce meses para el selector del reporte (siempre todos: un mes sin datos lo explica el servidor). */
export const MONTH_OPTIONS: readonly { value: number; label: string }[] = MONTH_NAMES.map((_, index) => ({ value: index + 1, label: monthTitle(index + 1) }));

// --- Puntos básicos → porcentaje (aritmética entera, sin decimales de coma flotante) -----------------------------------------------------

/** `2000` → `20,0 %`; `26050` → `260,5 %`. Redondeo a décimas *half-up* con enteros (`…,95` arrastra a la unidad siguiente). */
export function formatBp(bp: number): string {
  const abs = Math.abs(Math.trunc(bp));
  let whole = Math.floor(abs / 100);
  let tenths = Math.floor(((abs % 100) + 5) / 10);
  if (tenths === 10) {
    whole += 1;
    tenths = 0;
  }
  return `${whole},${tenths} %`;
}

/** La variación frente al mes anterior, siempre con signo y con palabras; `null` es que el mes anterior no sirve de referencia. */
export function variationText(bp: number | null, previousMonth: number): string {
  if (bp === null) return "sin referencia del mes anterior";
  if (bp === 0) return `sin cambios frente a ${monthName(previousMonth)}`;
  const sign = bp > 0 ? "+" : "−";
  return `${sign}${formatBp(bp)} frente a ${monthName(previousMonth)}`;
}

/** La diferencia en euros frente al mes anterior, con signo y con palabras (`+260,50 € frente a agosto`); el importe es el del servidor. */
export function deltaText(cents: number, previousMonth: number): string {
  if (cents === 0) return `sin cambios frente a ${monthName(previousMonth)}`;
  return `${cents > 0 ? "+" : ""}${formatCents(cents)} frente a ${monthName(previousMonth)}`;
}

/** Cuando no hay mes anterior con actividad. */
export const NO_PREVIOUS_MONTH = "No hay un mes anterior con actividad con el que comparar.";

// --- Geometría (porcentajes enteros de anchura o altura) --------------------------------------------------------------------------------

/** El ancho de una barra, de 0 a 100: 0 si no hay nada que dibujar (cero, negativo o sin máximo) y al menos 1 si hay algo, para que se vea. */
export function barPercent(value: number, max: number): number {
  if (!Number.isSafeInteger(value) || !Number.isSafeInteger(max) || value <= 0 || max <= 0) return 0;
  return Math.max(1, Math.min(100, Math.round((value * 100) / max)));
}

/** La altura de las dos columnas de cada mes de la tendencia, con una escala común a ingresos y gastos. */
export function columnPercents(points: readonly Pick<TrendPoint, "total_cents" | "expenses_cents">[]): { income: number; expenses: number }[] {
  const max = points.reduce((top, point) => Math.max(top, point.total_cents, point.expenses_cents), 0);
  return points.map((point) => ({ income: barPercent(point.total_cents, max), expenses: barPercent(point.expenses_cents, max) }));
}

// --- Textos de los gráficos (`aria-label` y la tabla equivalente salen de los mismos datos) --------------------------------------------

function summarize(title: string, items: readonly { label: string; value: string }[], empty: string): string {
  return items.length === 0 ? `${title}: ${empty}.` : `${title}: ${items.map((item) => `${item.label}, ${item.value}`).join("; ")}.`;
}

const when = (report: Pick<MonthlyReport, "month" | "year">): string => `${monthName(report.month)} de ${report.year}`;

export function clientsSummary(report: Pick<MonthlyReport, "month" | "year" | "by_client">): string {
  return summarize(
    `Ingresos por cliente en ${when(report)}`,
    report.by_client.map((client) => ({ label: `${client.name} (${SCOPE_LABEL[client.scope]})`, value: formatCents(client.base_cents) })),
    "no hay facturas emitidas",
  );
}

export function scopesSummary(report: Pick<MonthlyReport, "month" | "year" | "scopes">): string {
  return summarize(
    `Ingresos por ámbito en ${when(report)}`,
    report.scopes.map((scope) => ({ label: SCOPE_LABEL[scope.scope], value: `${formatCents(scope.base_cents)}${scope.share_bp === null ? "" : `, ${formatBp(scope.share_bp)}`}` })),
    "sin datos",
  );
}

export function categoriesSummary(report: Pick<MonthlyReport, "month" | "year" | "expenses_by_category">): string {
  return summarize(
    `Gastos por categoría en ${when(report)}`,
    report.expenses_by_category.map((category) => ({ label: category.label, value: formatCents(category.expenses_cents) })),
    "no hay gastos",
  );
}

export function trendSummary(report: Pick<MonthlyReport, "trend">): string {
  return summarize(
    "Ingresos y gastos de los últimos meses",
    report.trend.map((point) => ({ label: `${monthTitle(point.month)} de ${point.year}`, value: `ingresos ${formatCents(point.total_cents)}, gastos ${formatCents(point.expenses_cents)}` })),
    "sin datos",
  );
}

/** El estado de un mes de la tendencia, escrito. */
export const trendStatus = (point: Pick<TrendPoint, "status">): string => statusLabel(point.status).toLowerCase();

// --- Lo que conviene apartar: sin importe (D-08) -------------------------------------------------------------------------------------------

export const SET_ASIDE_NOTE =
  "Orientativo. El IVA y el IRPF de lo que facturas no son dinero tuyo aunque esté en tu cuenta. Aquí no se calcula un importe a apartar: el borrador del trimestre enseña lo que sale hoy, casilla a casilla.";

export function quarterLinks(year: number, quarter: number): { modelo303: string; modelo130: string } {
  const q = quarter as Quarter;
  return { modelo303: quarterHref(year, q, "303"), modelo130: quarterHref(year, q, "130") };
}

export const EXPENSES_EMPTY = "No hay gastos registrados este mes.";
