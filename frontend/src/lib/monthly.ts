// La contabilidad mensual en la interfaz (SPEC-W-012 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y no calcula ningún importe: ni un total, ni un acumulado, ni un resultado. Aquí solo se lee el año y el mes de la
// dirección, se elige qué mes se enseña por defecto y se redactan los textos de estado y de cierre con lo que ya devolvió la API.
import type { components } from "@/api/schema";

export type MonthlyClosings = components["schemas"]["MonthlyClosings"];
export type MonthRow = components["schemas"]["MonthRow"];
export type MonthlyClosing = components["schemas"]["MonthlyClosing"];
export type ClientTotals = components["schemas"]["ClientTotalsOut"];
export type MonthStatus = MonthRow["status"];

const MIN_YEAR = 2000;
const MAX_YEAR = 9998;

export const MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"] as const;

/** `septiembre` (minúscula, para frases) para un mes de 1 a 12; vacío si no existe. */
export const monthName = (month: number): string => MONTH_NAMES[month - 1] ?? "";

/** `Septiembre` (para encabezados y filas). */
export function monthTitle(month: number): string {
  const name = monthName(month);
  return name === "" ? "" : name.charAt(0).toUpperCase() + name.slice(1);
}

export type MonthlyQuery = { year: number; month: number | null };

const first = (value: string | string[] | undefined): string | undefined => (Array.isArray(value) ? value[0] : value);

/**
 * `?anio=&mes=`: cada parámetro por su cuenta. Lo ausente o ilegible del año vale el de hoy en Madrid (`today`, `AAAA-MM-DD`); un mes ilegible no elige ninguno
 * (la página enseña el último cerrado). Un año futuro SÍ se pasa tal cual: el servidor lo rechaza con su texto.
 */
export function parseMonthlyQuery(params: Record<string, string | string[] | undefined>, today: string): MonthlyQuery {
  const rawYear = first(params["anio"]);
  const rawMonth = first(params["mes"]);
  const currentYear = Number(today.slice(0, 4));
  const year = rawYear !== undefined && /^\d{4}$/.test(rawYear) && Number(rawYear) >= MIN_YEAR && Number(rawYear) <= MAX_YEAR ? Number(rawYear) : currentYear;
  const month = rawMonth !== undefined && /^(?:[1-9]|1[0-2])$/.test(rawMonth) ? Number(rawMonth) : null;
  return { year, month };
}

/** El mes que se enseña: el pedido si está en la lista; si no, el último cerrado y, si no hay ninguno, el último de la lista. */
export function chooseMonth(rows: readonly MonthRow[], requested: number | null): MonthRow | null {
  const asked = rows.find((row) => row.month === requested);
  if (asked) return asked;
  const closed = rows.filter((row) => row.status === "closed");
  return closed[closed.length - 1] ?? rows[rows.length - 1] ?? null;
}

export const monthHref = (year: number, month: number): string => `/mensual?anio=${year}&mes=${month}`;

const STATUS_LABEL: Record<MonthStatus, string> = { closed: "Cerrado", in_progress: "En curso", pending: "Pendiente de cierre" };
export const statusLabel = (status: MonthStatus): string => STATUS_LABEL[status];

/** Cuándo se cierra el mes: el 1 del siguiente (con el año si es diciembre). */
function closingDay(year: number, month: number): string {
  return month === 12 ? `1 de enero de ${year + 1}` : `1 de ${monthName(month + 1)}`;
}

/** La nota bajo el resultado de un mes: cuándo se cierra o se cerró y qué pasa si llega un documento atrasado. */
export function closingNote(row: Pick<MonthRow, "month" | "status" | "revision">, year: number): string {
  if (row.status === "in_progress") return `Este mes se cerrará automáticamente el ${closingDay(year, row.month)}.`;
  if (row.status === "pending") return "Este mes ya ha terminado y se cerrará en la próxima ejecución diaria del cierre automático.";
  const base = `Cerrado automáticamente el ${closingDay(year, row.month)}. Si llega una factura o un gasto atrasado, el mes se reabre y se vuelve a cerrar.`;
  return row.revision !== null && row.revision > 1 ? `${base} Se ha vuelto a cerrar ${row.revision - 1} ${row.revision - 1 === 1 ? "vez" : "veces"} (revisión ${row.revision}).` : base;
}

/** El aviso bajo la tabla: los cierres automáticos solo recalculan los últimos 12 meses. */
export const COVERAGE_NOTE =
  "El cierre automático recalcula cada día los últimos 12 meses. Los ingresos son bases imponibles, sin IVA; los gastos incluyen el IVA que no puedes deducir.";
